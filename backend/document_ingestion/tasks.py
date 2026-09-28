"""Tâches Celery du pilier d'ingestion.

Chaque tâche reçoit un identifiant, jamais une instance : elle recharge sa
ligne, ce qui la rend rejouable telle quelle après la mort d'un worker. La
logique métier reste dans `pipeline.process_ingest_job` ; la tâche n'est
qu'une enveloppe qui gère l'état du job et les réessais.
"""

from __future__ import annotations

import hashlib
import io
import logging
import shutil

from celery import chain, chord, group, shared_task
from django.conf import settings

from document_ingestion.blob_storage import open_stream, save_stream
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


# --- Rendu des pages en images privees ---------------------------------------


def page_image_storage_key(page: DocumentPage) -> str:
    """Cle privee deterministe, alignee sur celle du fichier source."""
    prefix = getattr(settings, "DOCUMENT_STORAGE_KEY_PREFIX", "documents")
    return (
        f"{prefix}/{page.version.document_id}/versions/"
        f"{page.version.version_label}/pages/{page.page_number:04d}.webp"
    )


def render_page_to_webp(pdf_stream, page_number: int, width: int) -> bytes:
    """Rend une page en WebP a la largeur demandee."""
    import pymupdf
    from PIL import Image

    document = pymupdf.open(stream=pdf_stream.read(), filetype="pdf")
    try:
        page = document[page_number - 1]
        zoom = width / page.rect.width if page.rect.width else 1
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    finally:
        document.close()

    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=80, method=4)
    return buffer.getvalue()


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def render_page_image(self, page_id: int) -> bool:
    """Produit l'image privee d'une page.

    Le rendu est un derive d'un fichier prive : il reste prive lui aussi et
    n'est servi qu'a travers une session de lecture autorisee. Rejouable :
    une image au contenu identique est conservee telle quelle.
    """
    page = DocumentPage.objects.select_related("version").get(pk=page_id)
    width = int(getattr(settings, "DOCUMENT_PAGE_IMAGE_WIDTH", 1240))

    source = (
        DocumentAsset.objects.filter(
            version=page.version, asset_type=DocumentAsset.AssetType.SOURCE_PDF
        )
        .order_by("id")
        .first()
    )
    if source is None:
        logger.warning("Page %s : aucun fichier source, rendu impossible.", page_id)
        return False

    with open_stream(source.storage_key) as handle:
        payload = render_page_to_webp(handle, page.page_number, width)

    checksum = hashlib.sha256(payload).hexdigest()
    existing = DocumentAsset.objects.filter(
        page=page, asset_type=DocumentAsset.AssetType.PAGE_IMAGE
    ).first()
    if existing is not None and existing.checksum_sha256 == checksum:
        logger.debug("Page %s : image inchangee, rien a reecrire.", page_id)
        return False

    storage_key = page_image_storage_key(page)
    save_stream(storage_key, io.BytesIO(payload))

    defaults = {
        "version": page.version,
        "storage_bucket": getattr(settings, "DOCUMENT_STORAGE_BUCKET", ""),
        "storage_key": storage_key,
        "mime_type": "image/webp",
        "byte_size": len(payload),
        "checksum_sha256": checksum,
        "visibility": DocumentAsset.Visibility.PRIVATE,
    }
    DocumentAsset.objects.update_or_create(
        page=page,
        asset_type=DocumentAsset.AssetType.PAGE_IMAGE,
        defaults=defaults,
    )
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
        render_page_image.si(page_id),
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
        render_page_image.run(page.pk)
        index_page.run(page.pk)
    mark_version_current_and_index(job.version)
