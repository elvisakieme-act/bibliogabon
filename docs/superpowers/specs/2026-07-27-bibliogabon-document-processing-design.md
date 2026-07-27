# BiblioGABON Document Processing Design

## Purpose

This slice creates the durable processing foundation for document pages, extracted text, and internal indexing records. It starts after private ingestion and before the secure reader. It records what later PDF, EPUB, OCR, rendering, and search workers will produce, but it does not run those workers yet.

## Product Rules

Raw source files remain private. Processing outputs are internal technical records unless a future reader API checks entitlement and returns controlled access. No page, text, or index record should expose a public file URL or signed URL in this slice.

Processing must be traceable from:

- a `document_ingestion.DocumentVersion`;
- a `document_ingestion.ProcessingJob`, when available;
- each page number;
- extracted text metadata;
- a deterministic content hash for index refresh decisions.

The catalog remains the owner of publication status and rights readiness. Processing can make a version technically usable, but it cannot publish content.

## Architecture

Create a dedicated Django app named `document_processing`. It depends on `document_ingestion` but `catalog` and `document_ingestion` must not import it.

Core models:

- `DocumentPage`: one logical page in a processed document version.
- `ExtractedText`: text extracted for one page, with language, method, confidence, and source job metadata.
- `SearchIndexRecord`: durable internal record showing what page text should be indexed and whether the index refresh is queued, indexed, or failed.

Primary services:

```python
create_page_records(version, page_count, created_by_job=None) -> list[DocumentPage]
attach_extracted_text(page, text, language_code="fr", extraction_method="text_layer", confidence=None, created_by_job=None) -> ExtractedText
queue_page_index_record(page) -> SearchIndexRecord
```

Services are synchronous and database-only. They prepare contracts for future Celery workers without adding Celery execution.

## Validation

Page numbers are positive and unique per version. Page records update the source version's `page_count` so later workflows can rely on one canonical count.

Extracted text must not be blank. A text extraction job, when supplied, must belong to the same document version as the page. Confidence must be between 0 and 1 when supplied.

Index records require extracted text and store a SHA-256 hash of that text. Re-queuing the same page must be idempotent; changing page text must refresh the stored hash and return the record to `queued`.

## Testing

Use pytest and pytest-django. Tests must prove:

- the app is installed;
- page creation is ordered, positive, unique, and idempotent;
- page creation updates `DocumentVersion.page_count`;
- extracted text rejects blank content and cross-version jobs;
- confidence validation rejects values outside 0..1;
- index records require extracted text;
- index records are idempotent for unchanged text and refresh for changed text;
- processing models are registered in Django admin.

## Out Of Scope

- Real PDF or EPUB parsing.
- OCR engines, page image rendering, thumbnails, or cover generation.
- Search backend integration and query APIs.
- Reader sessions, page delivery, signed URLs, offline packages, or anti-download controls.
- Entitlement checks, billing, analytics, and audit log implementation.
