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

from django.db import transaction
from django.utils import timezone

from document_ingestion.blob_storage import open_stream, save_stream
from document_ingestion.models import DocumentVersion, ProcessingJob
from document_ingestion.services import register_private_upload
from document_ingestion.storage import build_private_storage_key
from document_processing.models import DocumentPage
from document_processing.services import (
    attach_extracted_text,
    create_page_records,
    queue_page_index_record,
)
from search_discovery.services import rebuild_document_search_index

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


def _extract_pdf_page_texts(source) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dépend de l'environnement
        raise RuntimeError(
            "pypdf n'est pas installé. Lance : pip install pypdf"
        ) from exc

    reader = PdfReader(source)
    return [(page.extract_text() or "").strip() for page in reader.pages]


def process_ingest_job(job: ProcessingJob) -> DocumentVersion:
    """Traite un job d'ingestion : découpe en pages, extrait le texte, indexe.

    C'est cette fonction qui deviendra le corps d'une tâche Celery.
    """
    version = job.version
    source_asset = job.source_asset
    if source_asset is None:
        job.mark_failed(error_code="no_source_asset", message="Le job n'a pas de fichier source.")
        raise ValueError("Le job d'ingestion n'a pas de fichier source associé.")

    job.mark_started()
    try:
        with open_stream(source_asset.storage_key) as handle:
            page_texts = _extract_pdf_page_texts(handle)
        page_count = len(page_texts)
        if page_count < 1:
            raise ValueError("Le PDF ne contient aucune page exploitable.")

        language_code = version.document.language_code or "fr"

        with transaction.atomic():
            pages = create_page_records(version=version, page_count=page_count, created_by_job=job)
            for page, raw_text in zip(pages, page_texts):
                text = raw_text or EMPTY_PAGE_PLACEHOLDER.format(n=page.page_number)
                attach_extracted_text(
                    page=page,
                    text=text,
                    language_code=language_code,
                    created_by_job=job,
                )
                page.status = DocumentPage.Status.PROCESSED
                page.save(update_fields=["status", "updated_at"])
                queue_page_index_record(page=page)

            # Cette version devient l'unique version courante du document.
            DocumentVersion.objects.filter(document=version.document).exclude(pk=version.pk).update(
                is_current=False
            )
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
            rebuild_document_search_index(version.document)

        job.mark_completed(output_asset_ids=[])
        return version
    except Exception as exc:  # on trace l'échec dans le job puis on relaie
        job.mark_failed(error_code="ingest_failed", message=str(exc))
        raise


def ingest_document_file(
    *,
    document,
    fileobj,
    original_filename: str,
    mime_type: str = "application/pdf",
    uploaded_by=None,
    version_label: str = "v1",
) -> DocumentVersion:
    """Point d'entrée haut niveau : stocke le fichier, enregistre la version et
    l'asset, puis lance le traitement. Renvoie la version traitée.

    `fileobj` est un flux binaire repositionnable : la clé de stockage dépend
    de l'empreinte du contenu, donc on le parcourt une fois pour l'empreinte
    puis une seconde fois pour l'écriture. Rien n'est jamais entièrement
    chargé en mémoire.

    Passage à l'asynchrone plus tard : remplacer l'appel direct à
    `process_ingest_job(job)` par la mise en file d'une tâche Celery.
    """
    if not fileobj.seekable():
        raise ValueError("Le flux source doit être repositionnable (seekable).")

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
    return process_ingest_job(job)