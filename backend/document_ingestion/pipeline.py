"""Moteur d'ingestion : transforme un PDF en pages lisibles + texte indexé.

Aujourd'hui, tout tourne de façon SYNCHRONE (dans le processus web ou une
commande). C'est volontaire : la logique métier est isolée dans
`process_ingest_job`, qui deviendra tel quel le corps d'une tâche Celery le jour
où tu ajoutes Redis + Celery — sans rien changer d'autre.

Limite actuelle : l'extraction se fait sur la couche texte du PDF (documents
« nés numériques »). Les PDF scannés (images) ressortiront avec des pages vides
remplacées par un texte de remplacement — c'est là qu'interviendra l'OCR
(Tesseract) dans une itération suivante.
"""

from __future__ import annotations

import hashlib
import logging

from django.db import transaction
from django.utils import timezone

from document_ingestion.blob_storage import get_document_storage, open_stream, save_stream
from document_ingestion.exceptions import VersionAlreadyIngested
from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob
from document_ingestion.services import register_private_upload
from document_ingestion.storage import build_private_storage_key
from document_processing.models import DocumentPage, ExtractedText, SearchIndexRecord
from document_processing.services import (
    attach_extracted_text,
    create_page_records,
    queue_page_index_record,
)

logger = logging.getLogger(__name__)

EMPTY_PAGE_PLACEHOLDER = "[Page {n} : aucun texte extractible — OCR requis]"
CHUNK_SIZE = 1024 * 1024


def _checksum_and_size(fileobj) -> tuple[str, int]:
    """Empreinte et taille calculées en streaming, sans charger le fichier."""
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: fileobj.read(CHUNK_SIZE), b""):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _normalized_word_boxes(page) -> list[list]:
    """Position de chaque mot, en fractions de la page.

    Des fractions et non des pixels : la largeur de rendu est un réglage
    (`DOCUMENT_PAGE_IMAGE_WIDTH`), et des positions en pixels se décaleraient
    en silence le jour où il change — un défaut qui n'apparaîtrait qu'à la
    lecture, loin de sa cause.
    """
    width = page.rect.width
    height = page.rect.height
    if not width or not height:
        return []
    boxes = []
    for x0, y0, x1, y1, word, *_ in page.get_text("words"):
        if not word.strip():
            continue
        boxes.append(
            [
                round(min(max(x0 / width, 0.0), 1.0), 4),
                round(min(max(y0 / height, 0.0), 1.0), 4),
                round(min(max(x1 / width, 0.0), 1.0), 4),
                round(min(max(y1 / height, 0.0), 1.0), 4),
                word,
            ]
        )
    return boxes


def _extract_pdf_pages(source) -> list[tuple[str, list[list]]]:
    """Texte **et** position des mots, en une seule passe.

    Une seule bibliothèque pour les deux, volontairement. Une version
    antérieure lisait le texte avec pypdf et n'avait pas de positions ; y
    ajouter PyMuPDF pour les seules positions aurait fait décrire la même page
    par deux extracteurs, et un lecteur aurait fini par sélectionner un mot
    absent du texte indexé.

    Les deux extracteurs ont été comparés sur 160 pages réelles avant
    l'échange : les écarts étaient uniquement des espaces (similarité 0,998),
    sans effet ni sur la recherche, qui normalise, ni sur le seuil d'OCR, qui
    compte les caractères.
    """
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - dépend de l'environnement
        raise RuntimeError("pymupdf n'est pas installé. Lance : pip install pymupdf") from exc

    document = pymupdf.open(stream=source.read(), filetype="pdf")
    try:
        return [
            ((page.get_text() or "").strip(), _normalized_word_boxes(page)) for page in document
        ]
    finally:
        document.close()


def process_ingest_job(job: ProcessingJob) -> DocumentVersion:
    """Traite un job d'ingestion : découpe en pages, extrait le texte, indexe.

    C'est cette fonction qui deviendra le corps d'une tâche Celery.
    """
    version = job.version
    source_asset = job.source_asset
    if source_asset is None:
        job.mark_failed(
            error_code="no_source_asset", message="Le job n'a pas de fichier source."
        )
        raise ValueError("Le job d'ingestion n'a pas de fichier source associé.")

    job.mark_started()
    try:
        with open_stream(source_asset.storage_key) as handle:
            extracted_pages = _extract_pdf_pages(handle)
        page_count = len(extracted_pages)
        if page_count < 1:
            raise ValueError("Le PDF ne contient aucune page exploitable.")

        language_code = version.document.language_code or "fr"

        with transaction.atomic():
            pages = create_page_records(
                version=version, page_count=page_count, created_by_job=job
            )
            # strict=True : une divergence entre le nombre de pages creees
            # et le nombre de textes extraits laisserait sinon des pages
            # sans texte, sans la moindre erreur.
            for page, (raw_text, word_boxes) in zip(pages, extracted_pages, strict=True):
                text = raw_text or EMPTY_PAGE_PLACEHOLDER.format(n=page.page_number)
                attach_extracted_text(
                    page=page,
                    text=text,
                    language_code=language_code,
                    created_by_job=job,
                    word_boxes=word_boxes,
                )
                page.status = DocumentPage.Status.PROCESSED
                page.save(update_fields=["status", "updated_at"])
                # La file est consommee par `index_page`, en fin de chaine :
                # l'index doit voir le texte issu de l'OCR, pas celui d'avant.
                queue_page_index_record(page=page)

            version.status = DocumentVersion.Status.PROCESSED
            version.is_current = True
            version.page_count = page_count
            version.detected_format = "pdf"
            version.processed_at = timezone.now()
            version.processing_summary = f"{page_count} page(s) traitée(s)."
            version.save(
                update_fields=[
                    "status",
                    "is_current",
                    "page_count",
                    "detected_format",
                    "processed_at",
                    "processing_summary",
                    "updated_at",
                ]
            )
            # Les autres versions sont declassees et l'index du document
            # reconstruit par `finalize_version`, apres le travail par page.

        job.mark_completed(output_asset_ids=[])
        return version
    except Exception as exc:  # on trace l'échec dans le job puis on relaie
        job.mark_failed(error_code="ingest_failed", message=str(exc))
        raise


def _existing_ingested_version(document, version_label: str):
    """Renvoie la version deja peuplee pour ce libelle, s'il y en a une."""
    version = DocumentVersion.objects.filter(
        document=document, version_label=version_label
    ).first()
    if version is None:
        return None
    if DocumentPage.objects.filter(version=version).exists():
        return version
    return None


def _clear_version_content(version) -> None:
    """Vide une version de tout ce qu'une ingestion precedente y a depose.

    Les objets stockes partent avec les lignes : une version ne represente
    qu'un seul fichier source, donc conserver l'ancien laisserait deux
    sources contradictoires en base et un fichier prive orphelin que plus
    rien ne reference. L'ordre suit les dependances, le tout dans une
    transaction pour qu'un echec ne laisse pas une version a moitie videe.
    """
    storage = get_document_storage()
    storage_keys = list(
        DocumentAsset.objects.filter(version=version).values_list("storage_key", flat=True)
    )

    SearchIndexRecord.objects.filter(page__version=version).delete()
    ExtractedText.objects.filter(page__version=version).delete()
    DocumentPage.objects.filter(version=version).delete()
    DocumentAsset.objects.filter(version=version).delete()
    ProcessingJob.objects.filter(version=version).delete()

    # Apres le commit seulement : un rollback ne doit pas laisser la base
    # pointer vers des objets qu'on aurait deja supprimes du stockage.
    transaction.on_commit(lambda: _delete_stored_objects(storage, storage_keys))


def _delete_stored_objects(storage, storage_keys) -> None:
    for storage_key in storage_keys:
        try:
            if storage.exists(storage_key):
                storage.delete(storage_key)
        except Exception:  # le nettoyage ne doit jamais casser une ingestion
            logger.warning("Objet prive non supprime : %s", storage_key, exc_info=True)


def ingest_document_file(
    *,
    document,
    fileobj,
    original_filename: str,
    mime_type: str = "application/pdf",
    uploaded_by=None,
    version_label: str = "v1",
    replace: bool = False,
    dispatch: bool = True,
) -> DocumentVersion:
    """Point d'entrée haut niveau : stocke le fichier, enregistre la version et
    l'asset, puis lance le traitement. Renvoie la version traitée.

    `fileobj` est un flux binaire repositionnable : la clé de stockage dépend
    de l'empreinte du contenu, donc on le parcourt une fois pour l'empreinte
    puis une seconde fois pour l'écriture. Rien n'est jamais entièrement
    chargé en mémoire.

    `dispatch=True` met la chaîne complète en file : découpage, OCR,
    rendu des images, indexation, finalisation. En développement et en
    test les tâches s'exécutent en ligne, donc la version renvoyée est
    déjà traitée ; derrière un vrai broker elle revient en attente.

    `dispatch=False` déroule la même chaîne sans Celery, pour un
    contributeur qui n'a pas de worker sous la main.
    """
    if not fileobj.seekable():
        raise ValueError("Le flux source doit être repositionnable (seekable).")

    existing = _existing_ingested_version(document, version_label)
    if existing is not None:
        if not replace:
            raise VersionAlreadyIngested(existing)
        with transaction.atomic():
            _clear_version_content(existing)

    fileobj.seek(0)
    checksum, byte_size = _checksum_and_size(fileobj)
    storage_key = build_private_storage_key(
        document=document,
        version_label=version_label,
        original_filename=original_filename,
        checksum_sha256=checksum,
    )
    fileobj.seek(0)
    save_stream(storage_key, fileobj)

    register_private_upload(
        document=document,
        storage_key=storage_key,
        original_filename=original_filename,
        mime_type=mime_type,
        byte_size=byte_size,
        checksum_sha256=checksum,
        uploaded_by=uploaded_by,
        version_label=version_label,
    )
    job = ProcessingJob.objects.get(
        idempotency_key=f"ingest:{document.pk}:{version_label}:{checksum}"
    )

    from document_ingestion.tasks import dispatch_ingestion, run_ingestion_inline

    if dispatch:
        dispatch_ingestion(job.pk, job.version_id)
    else:
        run_ingestion_inline(job)

    job.version.refresh_from_db()
    return job.version
