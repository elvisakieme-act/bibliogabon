"""Tâches Celery du pilier d'ingestion.

Chaque tâche reçoit un identifiant, jamais une instance : elle recharge sa
ligne, ce qui la rend rejouable telle quelle après la mort d'un worker. La
logique métier reste dans `pipeline.process_ingest_job` ; la tâche n'est
qu'une enveloppe qui gère l'état du job et les réessais.
"""

from __future__ import annotations

import io
import logging
import shutil

from celery import chain, chord, group, shared_task
from django.conf import settings

from document_ingestion.blob_storage import delete_prefix, open_stream
from document_ingestion.iiif import (
    DEFAULT_TILE_WIDTH,
    tiles_root,
    write_page_tiles,
)
from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob
from document_ingestion.pipeline import process_ingest_job
from document_ingestion.services import mark_version_current_and_index
from document_processing.models import DocumentPage, ExtractedText
from document_processing.services import (
    attach_extracted_text,
    consume_page_index_record,
    fail_page_index_record,
    queue_page_index_record,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
# Backoff exponentiel borne : 30 s, 60 s, 120 s. Un PDF illisible ne doit pas
# monopoliser un worker, mais une panne passagere de stockage doit avoir le
# temps de se resorber.
RETRY_BASE_DELAY_SECONDS = 30
RETRY_MAX_DELAY_SECONDS = 600
# 200 dpi : assez pour Tesseract, sans faire exploser la memoire du worker.
OCR_RENDER_DPI = 200


def runs_inline() -> bool:
    """Vrai quand les tâches s'exécutent sans broker.

    Dans ce mode, Celery ne réexécute pas une tâche : reprogrammer un essai
    masquerait l'erreur d'origine derrière une exception `Retry`. On laisse
    donc remonter l'échec réel.
    """
    return bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False))


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def ingest_source_document(self, job_id: int) -> int:
    job = ProcessingJob.objects.get(pk=job_id)

    if job.status == ProcessingJob.Status.SUCCEEDED:
        logger.info("Job d'ingestion %s deja termine : rien a rejouer.", job_id)
        return job.version_id

    attempt = self.request.retries or 0
    job.celery_task_id = self.request.id or ""
    job.retry_count = attempt
    job.save(update_fields=["celery_task_id", "retry_count", "updated_at"])

    try:
        version = process_ingest_job(job)
    except Exception as exc:
        job.refresh_from_db()
        if runs_inline() or attempt >= MAX_RETRIES:
            job.mark_failed(
                error_code=job.error_code or "ingest_failed",
                message=job.error_message or str(exc),
                retry_count=attempt,
            )
            raise
        job.mark_retrying(
            error_code=job.error_code or "ingest_failed",
            message=job.error_message or str(exc),
            retry_count=attempt,
        )
        countdown = min(RETRY_BASE_DELAY_SECONDS * (2**attempt), RETRY_MAX_DELAY_SECONDS)
        raise self.retry(exc=exc, countdown=countdown) from exc

    return version.pk


# --- OCR ---------------------------------------------------------------------


def page_needs_ocr(page: DocumentPage) -> bool:
    """Une page a besoin d'OCR quand sa couche texte est absente ou trop
    maigre pour etre credible : un PDF numerise ressort avec zero caractere,
    un PDF mixte avec quelques artefacts."""
    text = ExtractedText.objects.filter(page=page).first()
    if text is None:
        return True
    if text.extraction_method == ExtractedText.ExtractionMethod.OCR:
        return False
    if text.text.startswith("[Page "):
        return True
    threshold = int(getattr(settings, "OCR_MIN_CHARACTERS", 20))
    return len(text.text.strip()) < threshold


def recognise_page(pdf_stream, page_number: int) -> tuple[str, float | None, list[list]]:
    """Rend la page en image puis la soumet a Tesseract.

    Renvoie le texte reconnu, une confiance moyenne ramenee sur 0..1, et la
    position de chaque mot en fractions de la page.

    Les positions ne coutent rien de plus : `image_to_data` les produisait
    deja et cette fonction les jetait. Une page reconnue par OCR a donc la
    meme couche texte selectionnable qu'une page a couche texte native, ce qui
    importe d'autant plus qu'un document scanne est precisement celui dont
    l'image seule serait inexploitable.
    """
    import pymupdf
    import pytesseract
    from PIL import Image

    languages = getattr(settings, "OCR_LANGUAGES", "fra") or "fra"
    document = pymupdf.open(stream=pdf_stream.read(), filetype="pdf")
    try:
        pixmap = document[page_number - 1].get_pixmap(dpi=OCR_RENDER_DPI)
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    finally:
        document.close()

    data = pytesseract.image_to_data(image, lang=languages, output_type=pytesseract.Output.DICT)
    words = [
        word
        for word, confidence in zip(data["text"], data["conf"], strict=True)
        if word.strip() and int(confidence) >= 0
    ]
    confidences = [int(c) for c in data["conf"] if int(c) >= 0]
    if not words:
        return "", None, []

    text = pytesseract.image_to_string(image, lang=languages)
    mean_confidence = sum(confidences) / len(confidences) / 100 if confidences else None
    return text, mean_confidence, ocr_word_boxes(data, image.width, image.height)


def ocr_word_boxes(data: dict, width: int, height: int) -> list[list]:
    """Positions Tesseract ramenees en fractions de la page.

    Tesseract repond en pixels de l'image qu'on lui a donnee, rendue a
    OCR_RENDER_DPI — une resolution differente de celle du rendu de lecture.
    Stocker ces pixels tels quels ferait decaler la couche texte des que l'une
    des deux resolutions changerait.
    """
    if not width or not height:
        return []
    boxes = []
    for index, word in enumerate(data["text"]):
        if not word.strip() or int(data["conf"][index]) < 0:
            continue
        left = data["left"][index]
        top = data["top"][index]
        boxes.append(
            [
                round(min(max(left / width, 0.0), 1.0), 4),
                round(min(max(top / height, 0.0), 1.0), 4),
                round(min(max((left + data["width"][index]) / width, 0.0), 1.0), 4),
                round(min(max((top + data["height"][index]) / height, 0.0), 1.0), 4),
                word,
            ]
        )
    return boxes


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def ocr_page(self, page_id: int) -> bool:
    """Reconnait le texte d'une page depourvue de couche texte.

    Renvoie True si la page a bien ete reconnue. Une page illisible garde
    son texte de remplacement — visible plutot que silencieusement vide —
    et son enregistrement d'index passe en echec, pour qu'une passe
    qualite puisse la retrouver.
    """
    page = DocumentPage.objects.select_related("version").get(pk=page_id)

    if not page_needs_ocr(page):
        logger.debug("Page %s : couche texte suffisante, OCR inutile.", page_id)
        return False

    if shutil.which("tesseract") is None:
        logger.warning(
            "Page %s : binaire tesseract introuvable, OCR ignore. "
            "Installez tesseract-ocr et le pack de langue correspondant.",
            page_id,
        )
        return False

    source = (
        DocumentAsset.objects.filter(
            version=page.version, asset_type=DocumentAsset.AssetType.SOURCE_PDF
        )
        .order_by("id")
        .first()
    )
    if source is None:
        logger.warning("Page %s : aucun fichier source, OCR impossible.", page_id)
        fail_page_index_record(page, "no_source_asset", "Aucun fichier source pour cette page.")
        return False

    with open_stream(source.storage_key) as handle:
        text, confidence, word_boxes = recognise_page(handle, page.page_number)

    if not text.strip():
        logger.info("Page %s : aucun texte reconnu par l'OCR.", page_id)
        fail_page_index_record(
            page, "ocr_empty", "L'OCR n'a reconnu aucun texte sur cette page."
        )
        return False

    attach_extracted_text(
        page=page,
        text=text,
        language_code=page.version.document.language_code or "fr",
        extraction_method=ExtractedText.ExtractionMethod.OCR,
        confidence=round(confidence, 3) if confidence is not None else None,
        word_boxes=word_boxes,
    )
    queue_page_index_record(page=page)
    return True


# --- Tuilage des pages ---------------------------------------------------------


def render_page_to_image(pdf_stream, page_number: int, width: int):
    """Rend une page a la largeur demandee, en image.

    Rendue en image et non en octets : le tuilage la decoupe, et la reencoder
    pour la redecouper ferait perdre de la qualite a chaque passage.
    """
    import pymupdf
    from PIL import Image

    document = pymupdf.open(stream=pdf_stream.read(), filetype="pdf")
    try:
        page = document[page_number - 1]
        zoom = width / page.rect.width if page.rect.width else 1
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
    finally:
        document.close()


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def tile_page(self, page_id: int) -> bool:
    """Produit le tuilage IIIF prive d'une page.

    Remplace le rendu d'une image unique par page. Celle-ci etait telechargee
    en entier pour etre vue en petit et bornait le zoom a sa largeur ; les
    tuiles ne descendent que ce qui est regarde et rendent le zoom illimite.

    Le derive reste prive et n'est servi qu'a travers une session de lecture
    autorisee, sauf la vignette, qui est la couverture publique d'un document
    decouvrable.

    Rejouable : l'arborescence precedente est effacee avant d'ecrire, faute de
    quoi une page devenue plus petite laisserait derriere elle des tuiles que
    `info.json` n'annonce plus.
    """
    page = DocumentPage.objects.select_related("version").get(pk=page_id)
    width = int(getattr(settings, "DOCUMENT_PAGE_IMAGE_WIDTH", DEFAULT_TILE_WIDTH))

    source = (
        DocumentAsset.objects.filter(
            version=page.version, asset_type=DocumentAsset.AssetType.SOURCE_PDF
        )
        .order_by("id")
        .first()
    )
    if source is None:
        logger.warning("Page %s : aucun fichier source, tuilage impossible.", page_id)
        return False

    with open_stream(source.storage_key) as handle:
        image = render_page_to_image(handle, page.page_number, width)

    delete_prefix(tiles_root(page))
    tiling = write_page_tiles(page, image)

    common = {
        "version": page.version,
        "storage_bucket": getattr(settings, "DOCUMENT_STORAGE_BUCKET", ""),
        "mime_type": "image/webp",
    }

    def record(asset_type, stored, visibility):
        DocumentAsset.objects.update_or_create(
            page=page,
            asset_type=asset_type,
            defaults={
                **common,
                "storage_key": stored.storage_key,
                "byte_size": stored.byte_size,
                "checksum_sha256": stored.checksum_sha256,
                "visibility": visibility,
            },
        )

    record(DocumentAsset.AssetType.PAGE_IMAGE, tiling.full, DocumentAsset.Visibility.PRIVATE)
    # La couverture pointe la vignette, pas la page entiere : une grille de
    # vingt couvertures ne doit pas coûter vingt pages a 300 ppp.
    record(DocumentAsset.AssetType.COVER, tiling.thumbnail, DocumentAsset.Visibility.PRIVATE)
    return True


# --- Indexation --------------------------------------------------------------


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def index_page(self, page_id: int) -> bool:
    return consume_page_index_record(DocumentPage.objects.get(pk=page_id))


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def finalize_version(self, version_id: int) -> int:
    version = DocumentVersion.objects.select_related("document").get(pk=version_id)
    mark_version_current_and_index(version)
    return version.pk


# --- Chaine complete ---------------------------------------------------------


def page_workflow(page_id: int):
    """Travail d'une page : reconnaitre le texte manquant, rendre l'image,
    puis consommer son enregistrement d'index. L'ordre compte — l'index doit
    voir le texte issu de l'OCR."""
    return chain(
        ocr_page.si(page_id),
        tile_page.si(page_id),
        index_page.si(page_id),
    )


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def process_version_pages(self, version_id: int):
    """Eclate le travail page par page, puis finalise une fois tout fini.

    La barriere est indispensable : `finalize_version` reconstruit l'index
    du document a partir des textes, donc il doit courir apres l'OCR.
    """
    page_ids = list(
        DocumentPage.objects.filter(version_id=version_id)
        .order_by("page_number")
        .values_list("pk", flat=True)
    )
    if not page_ids:
        return finalize_version.apply_async(args=[version_id])
    return chord(
        group(page_workflow(page_id) for page_id in page_ids),
        finalize_version.si(version_id),
    ).apply_async()


def dispatch_ingestion(job_id: int, version_id: int):
    """Met la chaine complete en file."""
    return chain(
        ingest_source_document.si(job_id),
        process_version_pages.si(version_id),
    ).apply_async()


def run_ingestion_inline(job) -> None:
    """Deroule la meme chaine sans passer par Celery.

    Pour un contributeur qui n'a pas de worker sous la main : meme ordre,
    memes fonctions, donc meme resultat.
    """
    process_ingest_job(job)
    for page in DocumentPage.objects.filter(version=job.version).order_by("page_number"):
        ocr_page.run(page.pk)
        tile_page.run(page.pk)
        index_page.run(page.pk)
    mark_version_current_and_index(job.version)
