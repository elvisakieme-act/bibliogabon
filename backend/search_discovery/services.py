from __future__ import annotations

from django.db import transaction
from django.db.models import Q
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


def _normalize_query(query: str) -> str:
    return " ".join(str(query or "").split()).lower()


def _contains(value: str, normalized_query: str) -> bool:
    return normalized_query in (value or "").lower()


def _bounded_limit(limit: int) -> int:
    limit = int(limit)
    if limit < 1:
        return 1
    return min(limit, 50)


def _score_index(index: DocumentSearchIndex, normalized_query: str) -> tuple[int, bool]:
    if not normalized_query:
        return 0, False

    score = 0
    if _contains(index.title, normalized_query):
        score += 1000
    if _contains(index.author_names, normalized_query):
        score += 100
    if _contains(index.domain_name, normalized_query) or _contains(index.domain_slug, normalized_query):
        score += 50
    if _contains(index.abstract, normalized_query):
        score += 20

    text_match = _contains(index.page_text, normalized_query)
    if text_match:
        score += 5
    return score, text_match


def _result_payload(index: DocumentSearchIndex, *, score: int, text_match: bool) -> dict:
    academic_domain = None
    if index.domain_name or index.domain_slug:
        academic_domain = {
            "name": index.domain_name,
            "slug": index.domain_slug,
        }

    return {
        "document_id": index.document_id,
        "title": index.title,
        "slug": index.slug,
        "abstract": index.abstract,
        "language_code": index.language_code,
        "publication_year": index.publication_year,
        "academic_domain": academic_domain,
        "authors": index.author_names.splitlines() if index.author_names else [],
        "access_model": index.document.access_model,
        "indexed_page_count": index.indexed_page_count,
        "score": score,
        "text_match": text_match,
    }


def search_documents(
    *,
    query: str = "",
    domain_slug: str = "",
    language_code: str = "",
    access_model: str = "",
    publication_year: int | None = None,
    limit: int | None = 20,
) -> list[dict]:
    normalized_query = _normalize_query(query)
    result_limit = _bounded_limit(limit) if limit is not None else None
    indexes = DocumentSearchIndex.objects.select_related("document").filter(
        document__publication_status=Document.PublicationStatus.PUBLISHED
    )
    indexes = indexes.exclude(document__access_model=Document.AccessModel.PRIVATE)

    if domain_slug:
        indexes = indexes.filter(domain_slug=domain_slug)
    if language_code:
        indexes = indexes.filter(language_code=language_code)
    if access_model:
        indexes = indexes.filter(document__access_model=access_model)
    if publication_year is not None:
        indexes = indexes.filter(publication_year=publication_year)
    if normalized_query:
        indexes = indexes.filter(
            Q(title__icontains=normalized_query)
            | Q(abstract__icontains=normalized_query)
            | Q(author_names__icontains=normalized_query)
            | Q(domain_name__icontains=normalized_query)
            | Q(domain_slug__icontains=normalized_query)
            | Q(metadata_text__icontains=normalized_query)
            | Q(page_text__icontains=normalized_query)
        )

    results = []
    for index in indexes:
        score, text_match = _score_index(index, normalized_query)
        results.append(_result_payload(index, score=score, text_match=text_match))

    results.sort(key=lambda result: (-result["score"], result["title"].lower(), result["document_id"]))
    return results if result_limit is None else results[:result_limit]
