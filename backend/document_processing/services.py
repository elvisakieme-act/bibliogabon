from __future__ import annotations

import hashlib

from django.db import transaction
from django.utils import timezone

from document_processing.models import DocumentPage, ExtractedText, SearchIndexRecord
from document_processing.text import normalize_extracted_text


def create_page_records(*, version, page_count: int, created_by_job=None) -> list[DocumentPage]:
    if page_count < 1:
        raise ValueError("page_count must be positive")
    if created_by_job is not None and created_by_job.version_id != version.pk:
        raise ValueError("created_by_job must belong to the same document version")

    with transaction.atomic():
        existing_numbers = list(
            DocumentPage.objects.select_for_update()
            .filter(version=version)
            .order_by("page_number")
            .values_list("page_number", flat=True)
        )
        if existing_numbers and existing_numbers != list(range(1, page_count + 1)):
            raise ValueError("Existing page records conflict with requested page_count")

        pages = []
        for page_number in range(1, page_count + 1):
            page, _ = DocumentPage.objects.get_or_create(
                version=version,
                page_number=page_number,
                defaults={"created_by_job": created_by_job},
            )
            pages.append(page)

        version.page_count = page_count
        version.save(update_fields=["page_count", "updated_at"])
        return pages


def attach_extracted_text(
    *,
    page: DocumentPage,
    text: str,
    language_code: str = "fr",
    extraction_method: str = ExtractedText.ExtractionMethod.TEXT_LAYER,
    confidence=None,
    created_by_job=None,
) -> ExtractedText:
    if not text or not text.strip():
        raise ValueError("text must not be blank")
    if created_by_job is not None and created_by_job.version_id != page.version_id:
        raise ValueError("created_by_job must belong to the same document version")

    # Point unique de normalisation : couche texte et OCR y passent tous deux,
    # donc aucun caractère de contrôle ne peut atteindre l'index ni le lecteur.
    text = normalize_extracted_text(text)
    if not text:
        raise ValueError("text must not be blank")

    extracted_text, _ = ExtractedText.objects.update_or_create(
        page=page,
        defaults={
            "text": text,
            "language_code": language_code,
            "extraction_method": extraction_method,
            "confidence": confidence,
            "created_by_job": created_by_job,
        },
    )
    return extracted_text


def queue_page_index_record(*, page: DocumentPage) -> SearchIndexRecord:
    try:
        extracted_text = ExtractedText.objects.get(page=page)
    except ExtractedText.DoesNotExist as exc:
        raise ValueError("page must have extracted text before indexing") from exc

    content_hash = hashlib.sha256(extracted_text.text.encode("utf-8")).hexdigest()

    with transaction.atomic():
        record, created = SearchIndexRecord.objects.select_for_update().get_or_create(
            page=page,
            defaults={
                "status": SearchIndexRecord.Status.QUEUED,
                "content_hash": content_hash,
                "language_code": extracted_text.language_code,
            },
        )
        if created:
            return record
        if (
            record.content_hash == content_hash
            and record.language_code == extracted_text.language_code
        ):
            return record

        record.status = SearchIndexRecord.Status.QUEUED
        record.content_hash = content_hash
        record.language_code = extracted_text.language_code
        record.indexed_at = None
        record.error_code = ""
        record.error_message = ""
        record.save(
            update_fields=[
                "status",
                "content_hash",
                "language_code",
                "indexed_at",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
        return record


def page_text_is_indexable(text: str) -> bool:
    """Un texte de remplacement signale une page illisible : l'indexer
    rendrait le document trouvable sur les mots du placeholder lui-meme."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    return not stripped.startswith("[Page ")


def fail_page_index_record(page: DocumentPage, error_code: str, message: str) -> None:
    record = SearchIndexRecord.objects.filter(page=page).first()
    if record is None:
        return
    record.status = SearchIndexRecord.Status.FAILED
    record.error_code = error_code
    record.error_message = message
    record.indexed_at = None
    record.save(
        update_fields=["status", "error_code", "error_message", "indexed_at", "updated_at"]
    )


def consume_page_index_record(page: DocumentPage) -> bool:
    """Vide l'enregistrement d'index d'une page.

    C'etait la piece manquante du pilier : la file se remplissait et rien
    ne la vidait. Une page illisible echoue explicitement, avec un motif,
    plutot que de rester indefiniment en attente.
    """
    record = SearchIndexRecord.objects.filter(page=page).first()
    if record is None:
        return False

    text = ExtractedText.objects.filter(page=page).first()
    if text is None:
        fail_page_index_record(
            page, "no_extracted_text", "Aucun texte extrait pour cette page."
        )
        return False

    if not page_text_is_indexable(text.text):
        fail_page_index_record(
            page,
            "no_extractable_text",
            "Page sans texte exploitable : exclue de l'index.",
        )
        return False

    if record.status == SearchIndexRecord.Status.INDEXED:
        return True

    record.status = SearchIndexRecord.Status.INDEXED
    record.indexed_at = timezone.now()
    record.error_code = ""
    record.error_message = ""
    record.save(
        update_fields=["status", "indexed_at", "error_code", "error_message", "updated_at"]
    )
    return True
