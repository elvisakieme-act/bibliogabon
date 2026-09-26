# BiblioGABON Ingestion Pillar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the asynchronous ingestion pillar — private object storage, Celery workers behind a Redis broker, page images, and OCR — and retire the synchronous stopgap in the task that replaces it.

**Architecture:** Keep the work inside `document_ingestion` and `document_processing`; no new Django app. Domain logic stays in plain service functions so Celery tasks remain thin, replayable wrappers around them. The storage backend is chosen by configuration behind an unchanged `storage_key` contract.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, Celery 5, Redis, boto3 + django-storages, PyMuPDF, pytesseract with tesseract-ocr-fra, pytest, pytest-django, moto for S3 in tests.

## Global Constraints

- Raw source files and generated page images stay private; no public URL, and no signed URL in reader payloads.
- Ingestion never publishes; `catalog` keeps publication authority.
- Every task is idempotent under replay: same id in, same result, no duplicated pages, assets or index rows.
- The stopgap pipeline is removed only in Task 9, once its replacement passes. The product must never be left without a content path.
- Tasks take ids, never model instances, and reload their rows.
- `CELERY_TASK_ALWAYS_EAGER` is on in development and tests, so no broker is needed to run the suite.
- Source files are streamed, never fully read into memory.
- Do not build an upload API, a deposit screen, EPUB support, thumbnails, signed URLs, Celery Beat schedules, or provision production infrastructure.
- Use TDD: write the failing test, run it red for the expected reason, implement, run green, then commit.

---

## File Structure

```text
backend/
  config/
    celery.py
    settings.py
    env.py
    tests/test_env.py
  document_ingestion/
    blob_storage.py
    pipeline.py
    tasks.py
    exceptions.py
    management/commands/
      ingest_file.py
      seed_demo.py
    tests/
      fixtures/sample-3-pages.pdf
      test_blob_storage.py
      test_reingestion.py
      test_tasks.py
      test_pipeline_end_to_end.py
  document_processing/
    services.py
    text.py
    tests/
      test_text_normalisation.py
      test_ocr.py
      test_page_images.py
      test_index_consumer.py
```

---

### Task 1: Dependencies And Configuration

**Files:**
- Modify: `backend/pyproject.toml`, `backend/requirements-lock.txt`, `backend/.env.example`
- Modify: `backend/config/settings.py`, `backend/config/env.py`
- Modify: `backend/config/tests/test_env.py`

**Interfaces:**
- Produces settings `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TASK_ALWAYS_EAGER`, `DOCUMENT_STORAGE_BACKEND`, `DOCUMENT_STORAGE_ENDPOINT_URL`, `DOCUMENT_PAGE_IMAGE_WIDTH`, `OCR_LANGUAGES`, `OCR_MIN_CHARACTERS`.
- Extends `validate_production_settings()` with broker and storage-backend checks.

- [x] Write failing tests: production rejects a missing `CELERY_BROKER_URL`, and rejects `DOCUMENT_STORAGE_BACKEND=filesystem`; development keeps working with neither set.
- [x] Add `celery`, `redis`, `boto3`, `django-storages[s3]`, `pymupdf`, `pytesseract` to `pyproject.toml`; add `moto` to the dev extra.
- [x] Regenerate `requirements-lock.txt` and confirm `pip install -r requirements-lock.txt` resolves.
- [x] Add the new settings with safe development defaults (`filesystem`, eager tasks).
- [x] Document every new variable in `.env.example`.
- [x] Note in the deployment checklist that production needs a broker, an S3 endpoint, and `tesseract-ocr-fra` on the host.
- [x] Run `pytest config/tests -q`, `manage.py check`.
- [x] Commit `chore: add ingestion pillar dependencies and settings`.

---

### Task 2: Configurable Streaming Storage

**Files:**
- Modify: `backend/document_ingestion/blob_storage.py`
- Create: `backend/document_ingestion/tests/test_blob_storage.py`

**Interfaces:**
- Produces `get_document_storage() -> Storage` selected by `DOCUMENT_STORAGE_BACKEND`.
- Produces `save_stream(storage_key, fileobj) -> None` and `open_stream(storage_key) -> IO[bytes]`.
- Retires `save_bytes` / `read_bytes`.

- [x] Write failing tests with `moto`: an object written under an S3 backend lands at the exact `storage_key`, is private, and round-trips; the filesystem backend behaves identically for the same key; an unknown backend name raises `ImproperlyConfigured`.
- [x] Write a failing test proving ingestion never materialises the whole file: feed a file-like object and assert the reader is consumed in chunks rather than via a single `.read()`.
- [x] Implement backend selection and the streaming helpers, keeping the existing delete-before-write guarantee so the key is exact under both backends.
- [x] Update `pipeline.py` call sites to the streaming API.
- [x] Run `pytest document_ingestion/tests -q`.
- [x] Commit `feat: select document storage backend by configuration`.

---

### Task 3: Extracted Text Normalisation

**Files:**
- Create: `backend/document_processing/text.py`, `backend/document_processing/tests/test_text_normalisation.py`
- Modify: `backend/document_processing/services.py`

**Interfaces:**
- Produces `normalize_extracted_text(text: str) -> str`.

- [x] Write failing tests using the real artefacts observed in production output: `\x13` and `\x14` become typographic quotes, other C0 control characters are stripped, runs of whitespace collapse, and text that is already clean is returned unchanged.
- [x] Implement the helper and call it inside `attach_extracted_text`, so every path — text layer and OCR alike — is normalised at one point.
- [x] Run `pytest document_processing/tests -q`.
- [x] Commit `fix: normalise extracted page text`.

---

### Task 4: Celery Application And Task Wrappers

**Files:**
- Create: `backend/config/celery.py`, `backend/document_ingestion/tasks.py`, `backend/document_ingestion/tests/test_tasks.py`
- Modify: `backend/config/__init__.py`, `backend/config/settings.py`

**Interfaces:**
- Produces the `celery_app`, autodiscovered tasks, and `ingest_source_document(job_id)`.

- [x] Write failing tests: the task resolves a job by id, delegates to `process_ingest_job`, and is safe to call twice for the same job; a task raising records `retry_count`, `error_code`, `error_message` and leaves the job `failed`; the suite runs with no broker because tasks are eager.
- [x] Implement `config/celery.py` reading configuration from Django settings under the `CELERY_` namespace.
- [x] Implement the task as a thin wrapper with explicit `self.retry`, exponential backoff, `max_retries` and `acks_late`.
      `autoretry_for` was rejected: under `task_always_eager` it never re-executes the task and replaces the real
      exception with `Retry`, which would hide every development failure behind a misleading error.
- [x] Make `retry_count` reflect real Celery retries instead of being set once.
- [x] Run `pytest document_ingestion/tests -q`.
- [x] Commit `feat: run ingestion through celery tasks`.

---

### Task 5: Safe Re-Ingestion

**Files:**
- Modify: `backend/document_ingestion/pipeline.py`, `backend/document_ingestion/exceptions.py`
- Modify: `backend/document_ingestion/management/commands/ingest_file.py`, `.../seed_demo.py`
- Create: `backend/document_ingestion/tests/test_reingestion.py`

**Interfaces:**
- Produces `VersionAlreadyIngested`.
- Produces `ingest_document_file(..., replace: bool = False)`.

- [ ] Write failing tests reproducing the recorded production failure: ingesting twice into `v1` raises `VersionAlreadyIngested` carrying the existing version, instead of `Existing page records conflict with requested page_count`; `replace=True` converges to exactly one set of pages, texts, index records and page assets; a new label creates a second version and leaves the first intact.
- [ ] Implement the typed exception and the transactional replace path.
- [ ] Add `--replace` to `ingest_file` and surface the conflict as a readable `CommandError`.
- [ ] Write a failing test asserting `seed_demo` creates zero `DocumentPage` rows; then strip page fabrication from the command and have it print the `ingest_file` invocation instead.
- [ ] Run `pytest document_ingestion/tests -q`.
- [ ] Commit `fix: make re-ingestion explicit instead of failing on collision`.

---

### Task 6: OCR For Pages Without A Text Layer

**Files:**
- Modify: `backend/document_ingestion/tasks.py`, `backend/document_processing/services.py`
- Create: `backend/document_processing/tests/test_ocr.py`
- Create: `backend/document_ingestion/tests/fixtures/sample-3-pages.pdf`

**Interfaces:**
- Produces `ocr_page(page_id)`.

- [ ] Add a small fixture PDF of three pages, one of them image-only. `.gitignore` blocks `*.pdf`, so add a negated rule for this path only, and keep the file under a few hundred kilobytes.
- [ ] Write failing tests: a page whose text layer is shorter than `OCR_MIN_CHARACTERS` is routed to OCR; OCR output is stored with `extraction_method=ocr` and a confidence in 0..1; a page OCR cannot read keeps a placeholder and a `failed` index record; re-running the task on an already-OCR'd page changes nothing.
- [ ] Implement the task using pytesseract with `OCR_LANGUAGES`, rendering the page through PyMuPDF before recognition.
- [ ] Skip gracefully with a clear log line when the tesseract binary is absent, so a contributor without it can still run the suite.
- [ ] Run `pytest document_processing/tests -q`.
- [ ] Commit `feat: OCR pages with no text layer`.

---

### Task 7: Page Image Rendering

**Files:**
- Modify: `backend/document_ingestion/tasks.py`, `backend/document_ingestion/models.py` if an asset type is missing
- Create: `backend/document_processing/tests/test_page_images.py`

**Interfaces:**
- Produces `render_page_image(page_id)`.

- [ ] Write failing tests: rendering a page creates one private `DocumentAsset` of type `page_image` linked to its page; the stored object is a WebP at `DOCUMENT_PAGE_IMAGE_WIDTH`; re-running skips when an asset with the same checksum exists; the asset is never exposed through any catalog, search or reader payload.
- [ ] Implement rendering with PyMuPDF, writing through `save_stream`.
- [ ] Add a regression test asserting no reader or catalog response contains a `page_image` key, a storage key or a URL.
- [ ] Run `pytest document_processing/tests document_reader/tests api/v1/tests -q`.
- [ ] Commit `feat: render private page images`.

---

### Task 8: Index Consumer

**Files:**
- Modify: `backend/document_ingestion/tasks.py`, `backend/search_discovery/services.py`
- Create: `backend/document_processing/tests/test_index_consumer.py`

**Interfaces:**
- Produces `index_page(page_id)` and `finalize_version(version_id)`.

- [ ] Write failing tests: `index_page` moves a record from `queued` to `indexed` and stamps `indexed_at`; a failure sets `failed` with a reason; replaying is idempotent; `finalize_version` rebuilds `DocumentSearchIndex` once from indexed pages and flips `is_current`; after a full ingestion no record is left `queued`.
- [ ] Implement both tasks and remove the inline `rebuild_document_search_index` call from the ingestion path, so one mechanism remains instead of two.
- [ ] Run `pytest document_processing/tests search_discovery/tests -q`.
- [ ] Commit `feat: consume the page index queue`.

---

### Task 9: Retire The Stopgap

**Files:**
- Modify: `backend/document_ingestion/pipeline.py`, `backend/document_ingestion/management/commands/ingest_file.py`
- Create: `backend/document_ingestion/tests/test_pipeline_end_to_end.py`

**Interfaces:**
- Produces the task chain `ingest_source_document -> (ocr_page | render_page_image | index_page) -> finalize_version`.

- [ ] Write the failing end-to-end test on the fixture PDF: every page has normalised text, the image-only page went through OCR, every page has a private image asset, no index record is `queued`, the version is `processed` and current, the job is `succeeded`, and a reader session serves a page with no storage field in the payload.
- [ ] Replace the synchronous body of `ingest_document_file` with the task chain; keep `process_ingest_job` as the per-job domain function the task calls.
- [ ] Delete the now-dead synchronous fan-out and the last `save_bytes` / `read_bytes` references.
- [ ] Point `ingest_file` at the chain, with `--sync` for a developer with no worker running.
- [ ] Run the full suite, `manage.py check`, `manage.py makemigrations --check --dry-run`.
- [ ] Commit `refactor: retire the synchronous ingestion stopgap`.

---

### Task 10: Documentation, Review And Finish

**Files:**
- Modify: `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/operations/deployment-checklist.md`
- Modify only files flagged by review findings.

- [ ] Document how to run a worker locally (`docker run redis:7-alpine`, `celery -A config worker -l info`) and how to ingest a file.
- [ ] Update the architecture notes: the pipeline is asynchronous, storage is configurable, OCR and page images exist.
- [ ] Record in `docs/product/00-decision-register.md` the decision to rebuild the pillar and the storage-provider arbitration left open.
- [ ] Request review focused on idempotency under replay, privacy of generated assets, storage-key stability, and migration safety.
- [ ] Verify each finding against the code before changing it; add a failing test for any behavioural fix.
- [ ] Rerun full verification: `pytest -q`, `manage.py check`, `manage.py makemigrations --check --dry-run`, `git diff --check`.
- [ ] Present finishing options for the branch.

---

## Self-Review Checklist

- [ ] No raw source file or generated image is reachable by a public or signed URL.
- [ ] Reader and catalog payloads still expose no storage key, URL or asset reference.
- [ ] Every task is idempotent when replayed with the same id.
- [ ] A failing task records retry count, error code and error message, and ends the job `failed`.
- [ ] Re-ingesting an existing version label is explicit, never a collision error.
- [ ] `seed_demo` creates no page records and cannot block ingestion.
- [ ] Extracted text is normalised on both the text-layer and OCR paths.
- [ ] Exactly one indexing mechanism remains, and no record is left `queued` after ingestion.
- [ ] Source files are streamed, never fully read into memory.
- [ ] The suite runs with no broker and no object storage, using eager tasks and `moto`.
- [ ] Production fails closed without a broker or an S3 backend.
- [ ] The synchronous stopgap is gone, and it was removed only once its replacement passed.
- [ ] No upload API, deposit screen, EPUB support, thumbnail or signed URL was added.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-26-bibliogabon-ingestion-pillar.md`.

Recommended execution: sequential TDD. Tasks 2 through 8 share `tasks.py` and the processing services, so parallel agents must not write to them concurrently. Tasks 1 and 3 are independent enough to run first in either order.

Task 9 is the only destructive step and depends on every preceding task being green. Do not start it while any earlier task is unfinished.
