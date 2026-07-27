from __future__ import annotations

from django.db import transaction

from document_processing.models import DocumentPage, ExtractedText


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
