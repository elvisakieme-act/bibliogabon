# BiblioGABON Document Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the database and service foundation for document pages, extracted text, and internal indexing records.

**Architecture:** Create a new Django app named `document_processing` that depends on `document_ingestion.DocumentVersion`, `document_ingestion.ProcessingJob`, and optionally `document_ingestion.DocumentAsset`. Keep processing state database-only and synchronous. Do not implement workers, OCR, rendering, reader APIs, signed URLs, or external search.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, pytest, pytest-django, SQLite local/test fallback, PostgreSQL production compatibility.

## Global Constraints

- Raw PDF/EPUB source files must remain private.
- Processing records must not store public or signed URLs.
- Processing does not publish a document; catalog rights and publication workflows remain authoritative.
- `document_processing` may import `document_ingestion`; `catalog` and `document_ingestion` must not import `document_processing`.
- Services must be idempotent where retries are expected.
- Each model must validate cross-version relationships before saving.
- Do not add OCR, PDF/EPUB parsing, rendering, Celery workers, external search, reader delivery, billing, analytics, or audit logs in this slice.

---

## File Structure

```text
backend/
  document_processing/
    __init__.py
    admin.py
    apps.py
    models.py
    services.py
    migrations/
      __init__.py
    tests/
      __init__.py
      test_admin_registration.py
      test_bootstrap.py
      test_extracted_text.py
      test_page_records.py
      test_search_index_records.py
  config/
    settings.py
  pyproject.toml
```

---

### Task 1: App Scaffold

**Files:**
- Create: `backend/document_processing/__init__.py`
- Create: `backend/document_processing/apps.py`
- Create: `backend/document_processing/migrations/__init__.py`
- Create: `backend/document_processing/tests/__init__.py`
- Create: `backend/document_processing/tests/test_bootstrap.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Produces installed Django app `document_processing`.

- [ ] Write a failing bootstrap test asserting `apps.is_installed("document_processing")`.
- [ ] Add `DocumentProcessingConfig`.
- [ ] Add `"document_processing"` to `INSTALLED_APPS`.
- [ ] Add `document_processing/tests` to pytest testpaths.
- [ ] Run the bootstrap test.
- [ ] Commit with `feat: add document processing app scaffold`.

---

### Task 2: Page Records

**Files:**
- Create: `backend/document_processing/models.py`
- Create: `backend/document_processing/services.py`
- Create: `backend/document_processing/tests/test_page_records.py`
- Generate: `backend/document_processing/migrations/0001_initial.py`

**Interfaces:**
- Produces `DocumentPage`.
- Produces `create_page_records(*, version, page_count, created_by_job=None) -> list[DocumentPage]`.

- [ ] Write failing tests for ordered page creation, positive page count validation, idempotent retries, uniqueness per version/page number, and version `page_count` update.
- [ ] Implement `DocumentPage` with positive `page_number`, status choices, optional `created_by_job`, and unique `(version, page_number)`.
- [ ] Validate `created_by_job.version_id == version_id` when a job is provided.
- [ ] Implement `create_page_records()` inside a transaction.
- [ ] Generate and run migrations.
- [ ] Run task tests.
- [ ] Commit with `feat: add document page records`.

---

### Task 3: Extracted Text

**Files:**
- Modify: `backend/document_processing/models.py`
- Modify: `backend/document_processing/services.py`
- Create: `backend/document_processing/tests/test_extracted_text.py`
- Generate: migration.

**Interfaces:**
- Produces `ExtractedText`.
- Produces `attach_extracted_text(*, page, text, language_code="fr", extraction_method="text_layer", confidence=None, created_by_job=None) -> ExtractedText`.

- [ ] Write failing tests for storing page text, updating existing page text, blank text rejection, invalid confidence rejection, and cross-version job rejection.
- [ ] Implement `ExtractedText` as one record per page.
- [ ] Store `text`, `language_code`, `extraction_method`, `confidence`, optional `created_by_job`, and timestamps.
- [ ] Call `full_clean()` on save.
- [ ] Implement `attach_extracted_text()` with idempotent `update_or_create`.
- [ ] Generate and run migrations.
- [ ] Run task tests.
- [ ] Commit with `feat: add extracted page text`.

---

### Task 4: Search Index Records

**Files:**
- Modify: `backend/document_processing/models.py`
- Modify: `backend/document_processing/services.py`
- Create: `backend/document_processing/tests/test_search_index_records.py`
- Generate: migration.

**Interfaces:**
- Produces `SearchIndexRecord`.
- Produces `queue_page_index_record(*, page) -> SearchIndexRecord`.

- [ ] Write failing tests proving indexing requires extracted text, creates a queued record with a hand-checked SHA-256 hash, re-queues unchanged text idempotently, and refreshes the hash when page text changes.
- [ ] Implement `SearchIndexRecord` as one record per page.
- [ ] Store `status`, `content_hash`, `language_code`, `indexed_at`, `error_code`, `error_message`, and timestamps.
- [ ] Implement `queue_page_index_record()` without calling any external search engine.
- [ ] Generate and run migrations.
- [ ] Run task tests.
- [ ] Commit with `feat: queue page search index records`.

---

### Task 5: Admin And Verification

**Files:**
- Create: `backend/document_processing/admin.py`
- Create: `backend/document_processing/tests/test_admin_registration.py`

**Interfaces:**
- Produces admin registration for `DocumentPage`, `ExtractedText`, and `SearchIndexRecord`.

- [ ] Write a failing admin registration test.
- [ ] Register processing models in Django admin with useful filters, search fields, and readonly timestamps.
- [ ] Run `pytest document_processing/tests -q`.
- [ ] Run full backend verification: `pytest -q`, `python manage.py check`, `python manage.py makemigrations --check --dry-run`, and `python manage.py migrate`.
- [ ] Commit with `feat: expose document processing in admin`.

## Self-Review Checklist

- [ ] Processing app is installed and covered by pytest testpaths.
- [ ] No raw, public, or signed URLs are stored or exposed.
- [ ] Page records are unique and ordered per document version.
- [ ] Version `page_count` is updated by page creation.
- [ ] Cross-version jobs are rejected.
- [ ] Text extraction rejects blank content and invalid confidence values.
- [ ] Index records are internal database records only.
- [ ] Re-queueing index records is idempotent and refreshes changed text.
- [ ] No OCR, renderer, reader, external search, Celery, billing, analytics, or audit implementation is added.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-27-bibliogabon-document-processing.md`.

Recommended execution: sequential TDD in this session. The tasks share one app and model file, so do not run implementation agents in parallel against the same write set.
