# BiblioGABON Document Ingestion Design

## Purpose

This slice creates the private ingestion foundation for BiblioGABON. It records uploaded source files, document versions, storage references, and processing jobs. It does not parse PDFs or EPUBs, generate pages, run OCR, expose signed URLs, build search indexes, or implement the reader.

## Product Rules

Raw files are private at every workflow state. A stored source file is an internal asset, never a public URL and never a reader response. Public users may discover approved metadata through `catalog`, but file access remains a future backend-controlled operation.

Every uploaded file must be traceable to:

- a `catalog.Document`;
- a version label;
- a private storage key;
- a checksum;
- MIME type and byte size;
- upload source;
- processing status;
- source retention policy.

Ingestion can happen before final publication, but it cannot make content public. Rights review and publication readiness remain owned by the catalog governance rules.

## Architecture

Create a dedicated Django app named `document_ingestion`. It references `catalog.Document` but does not change catalog publication rules. `catalog` must not import `document_ingestion`.

Core models:

- `DocumentVersion`: versioned technical package for one catalog document.
- `DocumentAsset`: private stored object reference for source files and future derivatives.
- `ProcessingJob`: durable job record for future Celery workers.

Primary service:

```python
register_private_upload(
    *,
    document,
    storage_key,
    original_filename,
    mime_type,
    byte_size,
    checksum_sha256,
    uploaded_by=None,
    version_label="v1",
) -> DocumentAsset
```

The service creates or reuses the document version, creates the private source asset, and creates an initial pending processing job. It rejects public-looking storage references such as `http://`, `https://`, or `file://`.

Storage key computation lives in `document_ingestion.storage` so S3-compatible storage can be added later without changing domain services:

```python
build_private_storage_key(document, version_label, original_filename, checksum_sha256) -> str
```

## Processing Model

`ProcessingJob` is only orchestration state in this slice. A future Celery task can consume pending jobs, but no worker is implemented now.

Required job data:

- job type;
- status;
- source asset;
- idempotency key;
- retry count;
- error code;
- error message;
- timestamps for creation, start, completion, and failure.

Jobs must support `mark_started()`, `mark_completed()`, and `mark_failed(error_code, message)` methods so later workers have a stable state transition API.

## Testing

Use pytest and pytest-django. Tests must prove:

- ingestion app is installed;
- document versions are unique per document and version label;
- document assets store private source metadata without raw public URLs;
- `register_private_upload()` creates asset, version, and pending job;
- duplicate uploads with the same checksum for the same version are idempotent;
- processing job creation is idempotent by idempotency key;
- invalid public storage keys are rejected;
- processing job state transitions record timestamps, retry count, and error data;
- ingestion models are registered in Django admin.

## Out Of Scope

- Real file upload endpoints and API serializers.
- S3 client integration and presigned URL generation.
- PDF/EPUB parsing, OCR, page rendering, thumbnails, and indexing.
- Reader sessions, page APIs, offline packages, and anti-download controls.
- Celery worker execution.
- Audit log subsystem and content moderation workflows.
