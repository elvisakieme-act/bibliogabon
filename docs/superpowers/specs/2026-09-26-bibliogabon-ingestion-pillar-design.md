# BiblioGABON Ingestion Pillar Design

## Purpose

This slice rebuilds the first backend pillar — the asynchronous ingestion pipeline — to the shape the product plan describes: private object storage, a message broker with background workers, page-by-page rendering to compressed images, and OCR for scanned documents.

It replaces the synchronous stopgap currently in `document_ingestion/pipeline.py`, which was written outside any plan and diverges from the pillar on five axes. The stopgap is removed in the task that supersedes it, never before, so the product is never left without a content path.

It does not build an upload API, a back-office deposit screen, or the publication workflow UI. Those belong to a later content-deposit slice that will call the services defined here.

## Why This Slice Exists

`docs/superpowers/specs/2026-07-27-bibliogabon-document-ingestion-design.md` and `...-document-processing-design.md` both placed parsing, OCR, rendering, indexing, and Celery execution explicitly out of scope, deferring them to "a future Celery task". That future slice was never planned. A working synchronous pipeline was added in its place without spec, plan, or test.

This document closes that gap. It keeps what the stopgap proved works and corrects what it got wrong.

### What the stopgap established

Measured on a 7.2 MB, 157-page PDF: 157 pages split, text extracted, version marked current, search index rebuilt, page served anonymously through the reader with no storage field exposed — in 4.8 seconds. The domain boundaries hold. Only the execution model and the media handling are wrong.

### Defects the rebuild must not reproduce

1. **Re-ingestion collides.** `create_page_records` refuses a version that already holds pages, so ingesting into an existing `version_label` fails with `Existing page records conflict with requested page_count`. This is the exact failure recorded on the only real run, caused by `seed_demo` having pre-filled the version.
2. **`SearchIndexRecord` has no consumer.** 157 rows were queued and none ever left `queued`; the real index is built by a direct call to `rebuild_document_search_index`. Two indexing mechanisms exist and one is dead.
3. **Extracted text is not normalised.** Control characters (`\x13`, `\x14`) reach `ExtractedText` and the search index in place of typographic quotes.
4. **`retry_count` is incremented but nothing retries.**
5. **The whole file is read into memory** as `bytes`, which does not survive a digitised institutional fund.

## Product Rules

Raw source files stay private at every state and are never addressable by a public URL. This is unchanged and non-negotiable.

Generated page images are derivatives of a private source and are themselves private. They are served only through an authorised reader session, exactly as page text is today. A page image must never be reachable by guessing a storage key, and the reader must not return a signed URL in this slice.

Ingestion never publishes. `catalog` remains the owner of publication status and rights readiness.

Every processing step must be idempotent under retry. A worker that dies mid-job and is replayed must converge to the same result, not duplicate pages, assets, or index rows.

OCR output is lower-trust than a text layer. Its extraction method and confidence must be recorded so a later quality pass can find and re-treat weak pages.

## Architecture

Work stays inside `document_ingestion` and `document_processing`. No new Django app.

### Storage

`document_ingestion.blob_storage` stops hard-coding `FileSystemStorage` and returns a backend chosen by configuration:

```python
get_document_storage() -> Storage
```

- `DOCUMENT_STORAGE_BACKEND=s3` selects `storages.backends.s3.S3Storage`, private, with `DOCUMENT_STORAGE_BUCKET`, `DOCUMENT_STORAGE_ENDPOINT_URL` and credentials from the environment.
- `DOCUMENT_STORAGE_BACKEND=filesystem` keeps the local backend for a developer with no object storage.

Which S3-compatible provider sits behind that endpoint is a deployment decision, not a code decision, and this slice must not encode one. See "Object Storage Choice" below.

The `storage_key` contract does not change, so existing rows stay valid. `save_stream`/`open_stream` replace `save_bytes`/`read_bytes` so a large source file is never fully materialised in memory.

### Queue

A Celery application lives in `config/celery.py`, broker and result backend from `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`. Tasks live in `document_ingestion/tasks.py`:

```python
ingest_source_document(job_id)   # split, extract text layer, fan out per page
ocr_page(page_id)                # pages whose text layer is empty
render_page_image(page_id)       # page -> compressed WebP derivative
index_page(page_id)              # consume the SearchIndexRecord queue
finalize_version(version_id)     # flip is_current, rebuild the document index
```

Each task takes an id, not an object, reloads its row, and is safe to replay. Each updates its `ProcessingJob`, honours `max_retries` with exponential backoff, and records `retry_count`, `error_code` and `error_message` on final failure.

`process_ingest_job()` keeps its current signature and stays the single place the domain logic lives; the Celery task is a thin wrapper around it. This is what the stopgap's docstring promised and it is worth keeping.

### Page rendering

PyMuPDF renders each page to WebP at a configured target width (`DOCUMENT_PAGE_IMAGE_WIDTH`, default 1240) and stores it as a `DocumentAsset` with `asset_type=page_image` and `visibility=private`, linked to its `DocumentPage`. Rendering is skipped when an asset with the same page and checksum already exists.

### OCR

`ocr_page` runs pytesseract with the French language pack on pages whose extracted text is empty or below a minimum character threshold. It writes `ExtractedText` with `extraction_method=ocr` and the mean Tesseract confidence normalised to 0..1. Pages that OCR cannot read keep an explicit placeholder and a failed index record, so they are findable rather than silently empty.

### Indexing

`index_page` is the missing consumer: it moves a `SearchIndexRecord` from `queued` to `indexed`, or to `failed` with a reason. `finalize_version` rebuilds `DocumentSearchIndex` once per version from indexed pages, instead of the inline call the stopgap makes per ingestion.

### Text normalisation

A shared `normalize_extracted_text(text) -> str` strips control characters, repairs the common PDF quote artefacts, collapses runs of whitespace, and is applied before any text reaches `ExtractedText`. Both the text-layer path and the OCR path go through it.

### Re-ingestion

`ingest_document_file` gains explicit semantics instead of failing on collision:

- a new `version_label` always creates a new version;
- an existing label with `replace=False` (default) raises a typed `VersionAlreadyIngested` carrying the existing version, so a caller can decide;
- `replace=True` deletes the previous pages, texts, index records, **every asset of that version including the
  source file, its stored object, and the stale processing job** inside one transaction, then re-ingests. A
  version represents one source file: keeping the previous one would record two contradictory sources and leak
  a private object nothing references. Stored objects are removed on commit, so a rollback never leaves the
  database pointing at deleted files.
- `PageAccessLog.page` becomes nullable with `SET_NULL`. Under `PROTECT` a document that had been read could
  not be re-ingested. The log already denormalises document, page number, user and timestamp, so the audit
  trail and the analytics aggregates survive the page row.

`seed_demo` stops fabricating page records. It seeds catalog metadata only and prints the `ingest_file` command to run for real content, so demo data can never again block ingestion.

## Configuration

New environment variables, documented in `backend/.env.example`:

- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`;
- `CELERY_TASK_ALWAYS_EAGER` — `True` in development and tests so the pipeline runs inline without a broker;
- `DOCUMENT_STORAGE_BACKEND`, `DOCUMENT_STORAGE_ENDPOINT_URL`, `DOCUMENT_STORAGE_ACCESS_KEY`, `DOCUMENT_STORAGE_SECRET_KEY`;
- `DOCUMENT_PAGE_IMAGE_WIDTH`, `OCR_LANGUAGES`, `OCR_MIN_CHARACTERS`.

Production must set a real broker and `DOCUMENT_STORAGE_BACKEND=s3`; `config.env.validate_production_settings` gains those two checks so production fails closed, consistent with the existing hardening.

## Environment Constraints

Verified in the current workspace on 2026-09-26:

- `redis:7-alpine` pulls and runs under Docker.
- `celery`, `redis`, `boto3`, `django-storages`, `moto`, `pymupdf`, `pytesseract` all install from PyPI.
- `tesseract-ocr`, `tesseract-ocr-fra` and `poppler-utils` install from apt.
- `chrislusf/seaweedfs`, `localstack/localstack` and `adobe/s3mock` all pull and run.
- **MinIO images are not pullable from this workspace** (denied on both docker.io and quay.io).

## Object Storage Choice

The code talks S3 through `boto3` and `django-storages`, so the provider is swappable by endpoint URL. The evaluation below informs deployment; it must not leak into application code.

SeaweedFS was benchmarked in this workspace on 2026-09-26 through its `weed server -s3` gateway with `boto3`. Every operation the pipeline needs passed: bucket creation, deeply nested keys, a 200 KB round trip, `Range` GET, `list_objects_v2`, `delete`, a 404 on `head` after delete, and presigned URL generation. Two hundred small objects wrote in 1.4 s (144/s).

SeaweedFS is the better self-hosted fit for this product:

- **Object profile.** Page rendering produces one WebP per page. Ten thousand documents at roughly 150 pages each is about 1.5 million objects of 50-200 KB. SeaweedFS packs small files into large volumes (the Haystack design), keeping per-file metadata overhead flat; MinIO stores one disk file per object, so inode and metadata pressure grows linearly with page count.
- **Licence.** Apache 2.0, against AGPLv3 for MinIO, whose community edition has also narrowed.
- **Footprint.** Lighter on the single production VM the product plan starts from.
- **Availability.** It actually installs here; MinIO does not.

MinIO keeps higher S3 fidelity and a far larger operator community. Neither advantage showed up on the operations this pipeline uses.

A managed S3-compatible service remains a serious alternative. The product plan rates storage and bandwidth cost a major risk, and Cloudflare R2 charges no egress, which attacks that risk directly and removes all storage operations work. The trade-off is against the documentary sovereignty principle and the national datacentre. That arbitration belongs to the product owner and does not block this slice.

Development and CI use `moto`, which needs no container at all. A developer who wants a realistic local object store runs SeaweedFS in Docker.

## Testing

Use pytest and pytest-django, with `CELERY_TASK_ALWAYS_EAGER` so tasks execute inline. Tests must prove:

- the storage backend is selected by configuration and the S3 path stores objects privately under the existing `storage_key`, using `moto`;
- switching `DOCUMENT_STORAGE_BACKEND` changes no caller: the same `storage_key` resolves under both backends;
- a source file is streamed, never fully read into memory;
- ingesting a real multi-page PDF produces one page, one normalised text and one index record per page;
- normalisation removes control characters and repairs quote artefacts;
- re-ingesting the same label raises `VersionAlreadyIngested`, and `replace=True` converges to a single clean set of pages;
- a page with no text layer is routed to OCR, and OCR output records method and confidence;
- an unreadable page keeps a placeholder and a failed index record;
- each task is idempotent when replayed with the same id;
- a task that raises records `retry_count`, `error_code` and `error_message`, and the job ends `failed`;
- page images are stored private, linked to their page, and skipped when already present;
- `index_page` moves records out of `queued` and `finalize_version` rebuilds the document index once;
- the reader still returns page text with no storage key, URL or signed URL in the payload;
- `seed_demo` creates no page records.

An end-to-end test ingests a small fixture PDF committed under `document_ingestion/tests/fixtures/` — a few pages, one of them image-only — and asserts the full chain. Large real PDFs are never committed; `.gitignore` already blocks `*.pdf`, so the fixture is added with an explicit exception.

## Out Of Scope

- Upload API endpoints and the back-office deposit screen.
- EPUB parsing.
- Signed URLs for page images; the reader keeps serving content through its session.
- Thumbnails, covers and any public derivative.
- Device concurrency limits and watermarking.
- Celery Beat schedules and periodic re-indexing.
- Provisioning Redis or object storage in production.
- Migrating the six demo documents currently in the development database.
