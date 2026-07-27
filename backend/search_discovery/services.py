from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from catalog.models import Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage, ExtractedText
from search_discovery.models import DocumentSearchIndex


def document_is_discoverable(document: Document) -> bool:
    return (
        document.publication_status == Document.PublicationStatus.PUBLISHED
        and document.access_model != Document.AccessModel.PRIVATE
    )


def _ordered_author_names(document: Document) -> list[str]:
    return list(
        document.document_authors.select_related("author")
        .order_by("position")
        .values_list("author__display_name", flat=True)
    )


def _metadata_text(*, document: Document, author_names: list[str]) -> str:
    parts = [
        document.title,
        document.abstract,
        document.academic_domain.name if document.academic_domain_id else "",
        *author_names,
    ]
    return "\n".join(part.strip() for part in parts if part and part.strip())


def _current_processed_version(document: Document) -> DocumentVersion | None:
    return (
        DocumentVersion.objects.filter(
            document=document,
            is_current=True,
            status=DocumentVersion.Status.PROCESSED,
        )
        .order_by("-created_at")
        .first()
    )


def _current_processed_page_text(document: Document) -> tuple[str, int]:
    version = _current_processed_version(document)
    if version is None:
        return "", 0

    extracted_texts = (
        ExtractedText.objects.filter(
            page__version=version,
            page__status=DocumentPage.Status.PROCESSED,
        )
        .select_related("page")
        .order_by("page__page_number")
    )
    page_texts = [text.text.strip() for text in extracted_texts if text.text and text.text.strip()]
    return "\n".join(page_texts), len(page_texts)


def rebuild_document_search_index(document: Document) -> DocumentSearchIndex | None:
    with transaction.atomic():
        if not document_is_discoverable(document):
            DocumentSearchIndex.objects.filter(document=document).delete()
            return None

        author_names = _ordered_author_names(document)
        page_text, indexed_page_count = _current_processed_page_text(document)
        domain = document.academic_domain if document.academic_domain_id else None

        index, _ = DocumentSearchIndex.objects.update_or_create(
            document=document,
            defaults={
                "title": document.title,
                "slug": document.slug,
                "abstract": document.abstract,
                "language_code": document.language_code,
                "publication_year": document.publication_year,
                "access_model": document.access_model,
                "domain_name": domain.name if domain else "",
                "domain_slug": domain.slug if domain else "",
                "author_names": "\n".join(author_names),
                "metadata_text": _metadata_text(document=document, author_names=author_names),
                "page_text": page_text,
                "indexed_page_count": indexed_page_count,
                "indexed_at": timezone.now(),
            },
        )
        return index


def rebuild_all_document_search_indexes() -> int:
    indexed_count = 0
    documents = Document.objects.select_related("academic_domain").prefetch_related(
        "document_authors__author"
    )
    for document in documents:
        if rebuild_document_search_index(document) is not None:
            indexed_count += 1
    return indexed_count
