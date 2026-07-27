# BiblioGABON Document Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the private document ingestion foundation for versioned source files, private storage references, and processing job orchestration.

**Architecture:** Create a dedicated Django app named `document_ingestion` that depends on `catalog.Document`. Store private object references as bucket/key metadata only; never store or expose raw file URLs. Keep services synchronous and testable now so Celery and S3 can be added later as adapters.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, pytest, pytest-django, SQLite local/test fallback, PostgreSQL production compatibility, future Redis/Celery and S3-compatible private storage.

## Global Constraints

- Raw PDF/EPUB files must stay private and must never be exposed directly.
- Upload does not equal publication; publication governance remains in `catalog`.
- `catalog` must not import `document_ingestion`.
- `document_ingestion` may reference `catalog.Document`.
- Store `storage_bucket` and `storage_key`, not public or signed URLs.
- Processing jobs must record status, retry count, error reason, and source object reference.
- Job creation must support idempotency for retries and future workers.
- Do not implement PDF/EPUB parsing, OCR, page rendering, search indexing, reader sessions, signed URLs, billing, or Celery workers in this slice.

---

## File Structure

```text
backend/
  document_ingestion/
    __init__.py
    admin.py
    apps.py
    models.py
    services.py
    storage.py
    migrations/
      __init__.py
    tests/
      __init__.py
      test_bootstrap.py
      test_storage_keys.py
      test_document_versions.py
      test_processing_jobs.py
      test_private_uploads.py
      test_admin_registration.py
  config/
    settings.py
  pyproject.toml
  pytest.ini
```

Responsibilities:

- `document_ingestion/storage.py`: deterministic private storage key construction and raw URL rejection helpers.
- `document_ingestion/models.py`: `DocumentVersion`, `DocumentAsset`, and `ProcessingJob`.
- `document_ingestion/services.py`: upload registration and job enqueue services.
- `document_ingestion/admin.py`: admin visibility for operations staff.

---

### Task 1: App Scaffold And Private Storage Keys

**Files:**
- Create: `backend/document_ingestion/__init__.py`
- Create: `backend/document_ingestion/apps.py`
- Create: `backend/document_ingestion/storage.py`
- Create: `backend/document_ingestion/migrations/__init__.py`
- Create: `backend/document_ingestion/tests/__init__.py`
- Create: `backend/document_ingestion/tests/test_bootstrap.py`
- Create: `backend/document_ingestion/tests/test_storage_keys.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/pytest.ini`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Consumes: `catalog.models.Document`.
- Produces: installed app and `build_private_storage_key(document, version_label, original_filename, checksum_sha256) -> str`.

- [ ] **Step 1: Write failing bootstrap test**

Create `backend/document_ingestion/tests/test_bootstrap.py`:

```python
from django.apps import apps


def test_document_ingestion_app_is_installed():
    assert apps.is_installed("document_ingestion")
```

- [ ] **Step 2: Write failing storage key tests**

Create `backend/document_ingestion/tests/test_storage_keys.py`:

```python
import pytest

from catalog.models import AcademicDomain, Document
from document_ingestion.storage import build_private_storage_key, storage_key_is_public_reference


@pytest.mark.django_db
def test_private_storage_key_is_deterministic_and_not_public_url():
    domain = AcademicDomain.objects.create(name="Informatique", slug="informatique-ingestion")
    document = Document.objects.create(
        title="Architecture numerique",
        slug="architecture-numerique",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.PRIVATE,
    )

    storage_key = build_private_storage_key(
        document=document,
        version_label="v1",
        original_filename="Memoire Final.pdf",
        checksum_sha256="a" * 64,
    )

    assert storage_key == f"documents/{document.pk}/versions/v1/aaaaaaaa/memoire-final.pdf"
    assert storage_key_is_public_reference(storage_key) is False


@pytest.mark.parametrize("value", ["http://example.com/file.pdf", "https://example.com/file.pdf", "file:///tmp/file.pdf"])
def test_public_references_are_rejected(value):
    assert storage_key_is_public_reference(value) is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd backend
pytest document_ingestion/tests/test_bootstrap.py document_ingestion/tests/test_storage_keys.py -q
```

Expected: FAIL because `document_ingestion` is not installed and `storage.py` does not exist.

- [ ] **Step 4: Create app shell and install app**

Create `backend/document_ingestion/apps.py`:

```python
from django.apps import AppConfig


class DocumentIngestionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "document_ingestion"
```

Create empty files:

```text
backend/document_ingestion/__init__.py
backend/document_ingestion/migrations/__init__.py
backend/document_ingestion/tests/__init__.py
```

Add `"document_ingestion"` to `INSTALLED_APPS` in `backend/config/settings.py`.

Add private storage configuration in `backend/config/settings.py`:

```python
DOCUMENT_STORAGE_BUCKET = os.getenv("DOCUMENT_STORAGE_BUCKET", "bibliogabon-private-documents")
DOCUMENT_STORAGE_KEY_PREFIX = os.getenv("DOCUMENT_STORAGE_KEY_PREFIX", "documents")
```

Update `backend/pytest.ini`:

```ini
testpaths = accounts/tests catalog/tests document_ingestion/tests
```

Update `[tool.pytest.ini_options]` in `backend/pyproject.toml`:

```toml
testpaths = ["accounts/tests", "catalog/tests", "document_ingestion/tests"]
```

- [ ] **Step 5: Implement storage helpers**

Create `backend/document_ingestion/storage.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings


PUBLIC_REFERENCE_PREFIXES = ("http://", "https://", "file://")


def storage_key_is_public_reference(value: str) -> bool:
    return value.lower().startswith(PUBLIC_REFERENCE_PREFIXES)


def slugify_filename(filename: str) -> str:
    path_name = Path(filename).name
    stem = Path(path_name).stem.lower()
    suffix = Path(path_name).suffix.lower()
    safe_stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return f"{safe_stem or 'document'}{suffix}"


def build_private_storage_key(
    *,
    document,
    version_label: str,
    original_filename: str,
    checksum_sha256: str,
) -> str:
    checksum_prefix = checksum_sha256[:8]
    filename = slugify_filename(original_filename)
    prefix = settings.DOCUMENT_STORAGE_KEY_PREFIX.strip("/")
    return f"{prefix}/{document.pk}/versions/{version_label}/{checksum_prefix}/{filename}"
```

- [ ] **Step 6: Run task tests**

Run:

```bash
cd backend
pytest document_ingestion/tests/test_bootstrap.py document_ingestion/tests/test_storage_keys.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/document_ingestion backend/config/settings.py backend/pytest.ini backend/pyproject.toml
git commit -m "feat: add document ingestion storage foundation"
```

---

### Task 2: Document Versions And Private Assets

**Files:**
- Create: `backend/document_ingestion/models.py`
- Create: `backend/document_ingestion/migrations/__init__.py`
- Create: `backend/document_ingestion/tests/test_document_versions.py`
- Generate: `backend/document_ingestion/migrations/0001_initial.py`

**Interfaces:**
- Consumes: `catalog.models.Document` and `settings.AUTH_USER_MODEL`.
- Produces: `DocumentVersion` and `DocumentAsset`.

- [ ] **Step 1: Write failing version and asset tests**

Create `backend/document_ingestion/tests/test_document_versions.py`:

```python
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentAsset, DocumentVersion


def create_document():
    domain = AcademicDomain.objects.create(name="Droit numerique", slug="droit-numerique")
    return Document.objects.create(
        title="Droit numerique gabonais",
        slug="droit-numerique-gabonais",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.PRIVATE,
    )


@pytest.mark.django_db
def test_document_version_is_unique_per_document_and_label():
    document = create_document()
    DocumentVersion.objects.create(document=document, version_label="v1")

    with pytest.raises(IntegrityError):
        DocumentVersion.objects.create(document=document, version_label="v1")


@pytest.mark.django_db
def test_source_asset_stores_private_object_metadata():
    version = DocumentVersion.objects.create(document=create_document(), version_label="v1")
    asset = DocumentAsset.objects.create(
        version=version,
        asset_type=DocumentAsset.AssetType.SOURCE_PDF,
        storage_bucket="bibliogabon-private-documents",
        storage_key="documents/1/versions/v1/abcd1234/source.pdf",
        mime_type="application/pdf",
        byte_size=2048,
        checksum_sha256="b" * 64,
    )

    assert asset.visibility == DocumentAsset.Visibility.PRIVATE
    assert asset.public_url == ""
    assert str(asset) == "source_pdf: documents/1/versions/v1/abcd1234/source.pdf"


@pytest.mark.parametrize("storage_key", ["http://example.com/source.pdf", "https://example.com/source.pdf", "file:///tmp/source.pdf"])
@pytest.mark.django_db
def test_asset_rejects_public_storage_reference(storage_key):
    version = DocumentVersion.objects.create(document=create_document(), version_label="v1")
    asset = DocumentAsset(
        version=version,
        asset_type=DocumentAsset.AssetType.SOURCE_PDF,
        storage_bucket="bibliogabon-private-documents",
        storage_key=storage_key,
        mime_type="application/pdf",
        byte_size=2048,
        checksum_sha256="c" * 64,
    )

    with pytest.raises(ValidationError):
        asset.full_clean()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest document_ingestion/tests/test_document_versions.py -q
```

Expected: FAIL because models do not exist.

- [ ] **Step 3: Implement models**

Create `backend/document_ingestion/models.py`:

```python
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from document_ingestion.storage import storage_key_is_public_reference


class DocumentVersion(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"
        SUPERSEDED = "superseded", "Superseded"

    class SourceRetentionPolicy(models.TextChoices):
        RETAIN_PRIVATE_SOURCE = "retain_private_source", "Retain private source"
        DELETE_AFTER_PROCESSING = "delete_after_processing", "Delete after processing"

    document = models.ForeignKey("catalog.Document", on_delete=models.CASCADE, related_name="versions")
    version_label = models.CharField(max_length=40)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.UPLOADED)
    is_current = models.BooleanField(default=True)
    source_retention_policy = models.CharField(
        max_length=32,
        choices=SourceRetentionPolicy.choices,
        default=SourceRetentionPolicy.RETAIN_PRIVATE_SOURCE,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_document_versions",
    )
    page_count = models.PositiveIntegerField(null=True, blank=True)
    detected_format = models.CharField(max_length=32, blank=True)
    processing_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["document", "version_label"], name="uniq_version_label_per_document")
        ]
        ordering = ["document__title", "-created_at"]

    def __str__(self) -> str:
        return f"{self.document.title} {self.version_label}"


class DocumentAsset(models.Model):
    class AssetType(models.TextChoices):
        SOURCE_RAW = "source_raw", "Source raw"
        SOURCE_PDF = "source_pdf", "Source PDF"
        SOURCE_EPUB = "source_epub", "Source EPUB"
        PAGE_IMAGE = "page_image", "Page image"
        OCR_TEXT = "ocr_text", "OCR text"
        COVER = "cover", "Cover"
        EPUB_PACKAGE = "epub_package", "EPUB package"
        DERIVED_FILE = "derived_file", "Derived file"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        INTERNAL = "internal", "Internal"

    version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name="assets")
    asset_type = models.CharField(max_length=24, choices=AssetType.choices)
    storage_bucket = models.CharField(max_length=160)
    storage_key = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=120)
    byte_size = models.PositiveBigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PRIVATE)
    public_url = models.URLField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "asset_type", "checksum_sha256"],
                name="uniq_asset_checksum_per_version_type",
            )
        ]
        ordering = ["version", "asset_type", "created_at"]

    def clean(self):
        if storage_key_is_public_reference(self.storage_key):
            raise ValidationError("Storage key must be a private object key, not a public reference")
        if self.public_url:
            raise ValidationError("Document assets must not store public URLs")
        if self.asset_type in {self.AssetType.SOURCE_RAW, self.AssetType.SOURCE_PDF, self.AssetType.SOURCE_EPUB}:
            if self.visibility != self.Visibility.PRIVATE:
                raise ValidationError("Source assets must remain private")

    def __str__(self) -> str:
        return f"{self.asset_type}: {self.storage_key}"
```

- [ ] **Step 4: Create migration**

Run:

```bash
cd backend
python manage.py makemigrations document_ingestion
```

Expected: Django creates `0001_initial.py` for `DocumentVersion` and `DocumentAsset`.

- [ ] **Step 5: Run task tests**

Run:

```bash
cd backend
pytest document_ingestion/tests/test_document_versions.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/document_ingestion
git commit -m "feat: add document ingestion version assets"
```

---

### Task 3: Processing Jobs And State Transitions

**Files:**
- Modify: `backend/document_ingestion/models.py`
- Create: `backend/document_ingestion/services.py`
- Create: `backend/document_ingestion/tests/test_processing_jobs.py`
- Generate: `backend/document_ingestion/migrations/0002_processingjob.py`

**Interfaces:**
- Consumes: `DocumentVersion` and `DocumentAsset`.
- Produces: `ProcessingJob`, `enqueue_processing_job(version, job_type, idempotency_key, source_asset=None, input_payload=None) -> ProcessingJob`.

- [ ] **Step 1: Write failing processing job tests**

Create `backend/document_ingestion/tests/test_processing_jobs.py`:

```python
import pytest

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob
from document_ingestion.services import enqueue_processing_job


def create_version_and_asset():
    domain = AcademicDomain.objects.create(name="Medecine numerique", slug="medecine-numerique")
    document = Document.objects.create(
        title="Sante numerique",
        slug="sante-numerique",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.PRIVATE,
    )
    version = DocumentVersion.objects.create(document=document, version_label="v1")
    asset = DocumentAsset.objects.create(
        version=version,
        asset_type=DocumentAsset.AssetType.SOURCE_PDF,
        storage_bucket="bibliogabon-private-documents",
        storage_key="documents/1/versions/v1/abcd1234/source.pdf",
        mime_type="application/pdf",
        byte_size=4096,
        checksum_sha256="d" * 64,
    )
    return version, asset


@pytest.mark.django_db
def test_enqueue_processing_job_is_idempotent_by_key():
    version, asset = create_version_and_asset()

    first = enqueue_processing_job(
        version=version,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key="document-1-v1-ingest",
        source_asset=asset,
    )
    second = enqueue_processing_job(
        version=version,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key="document-1-v1-ingest",
        source_asset=asset,
    )

    assert first.pk == second.pk
    assert ProcessingJob.objects.count() == 1
    assert first.status == ProcessingJob.Status.QUEUED


@pytest.mark.django_db
def test_processing_job_state_transitions_record_timestamps_and_errors():
    version, asset = create_version_and_asset()
    completed_job = enqueue_processing_job(
        version=version,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key="document-1-v1-complete",
        source_asset=asset,
    )

    completed_job.mark_started()
    assert completed_job.status == ProcessingJob.Status.RUNNING
    assert completed_job.started_at is not None

    completed_job.mark_completed(output_asset_ids=[12, 13])
    assert completed_job.status == ProcessingJob.Status.SUCCEEDED
    assert completed_job.output_asset_ids == [12, 13]
    assert completed_job.completed_at is not None

    failed_job = enqueue_processing_job(
        version=version,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key="document-1-v1-fail",
        source_asset=asset,
    )
    failed_job.mark_started()
    failed_job.mark_failed(error_code="parse_error", message="Unsupported file")
    assert failed_job.status == ProcessingJob.Status.FAILED
    assert failed_job.retry_count == 1
    assert failed_job.error_code == "parse_error"
    assert failed_job.error_message == "Unsupported file"
    assert failed_job.failed_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest document_ingestion/tests/test_processing_jobs.py -q
```

Expected: FAIL because `ProcessingJob` and `enqueue_processing_job()` do not exist.

- [ ] **Step 3: Implement `ProcessingJob` and service**

Append to `backend/document_ingestion/models.py`:

```python
class ProcessingJob(models.Model):
    class JobType(models.TextChoices):
        INGEST_SOURCE = "ingest_source", "Ingest source"
        EXTRACT_METADATA = "extract_metadata", "Extract metadata"
        GENERATE_DERIVATIVES = "generate_derivatives", "Generate derivatives"
        OCR = "ocr", "OCR"
        INDEX = "index", "Index"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        RETRYING = "retrying", "Retrying"
        CANCELLED = "cancelled", "Cancelled"

    version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name="processing_jobs")
    source_asset = models.ForeignKey(
        DocumentAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processing_jobs",
    )
    job_type = models.CharField(max_length=32, choices=JobType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    idempotency_key = models.CharField(max_length=180, unique=True)
    celery_task_id = models.CharField(max_length=180, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    input_payload = models.JSONField(default=dict, blank=True)
    output_asset_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def mark_started(self):
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_failed(self, *, error_code: str, message: str):
        self.status = self.Status.FAILED
        self.retry_count += 1
        self.error_code = error_code
        self.error_message = message
        self.failed_at = timezone.now()
        self.save(update_fields=["status", "retry_count", "error_code", "error_message", "failed_at", "updated_at"])

    def mark_completed(self, *, output_asset_ids=None):
        self.status = self.Status.SUCCEEDED
        self.output_asset_ids = output_asset_ids or []
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "output_asset_ids", "completed_at", "updated_at"])

    def __str__(self) -> str:
        return f"{self.job_type} for {self.version}"
```

Also add this nullable field to `DocumentAsset`:

```python
created_by_job = models.ForeignKey(
    "ProcessingJob",
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="created_assets",
)
```

Create `backend/document_ingestion/services.py`:

```python
from __future__ import annotations

from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob


def enqueue_processing_job(
    *,
    version: DocumentVersion,
    job_type: str,
    idempotency_key: str,
    source_asset: DocumentAsset | None = None,
    input_payload: dict | None = None,
) -> ProcessingJob:
    job, _ = ProcessingJob.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "version": version,
            "source_asset": source_asset,
            "job_type": job_type,
            "input_payload": input_payload or {},
        },
    )
    return job
```

- [ ] **Step 4: Create migration**

Run:

```bash
cd backend
python manage.py makemigrations document_ingestion
```

Expected: Django creates `0002_processingjob.py`.

- [ ] **Step 5: Run task tests**

Run:

```bash
cd backend
pytest document_ingestion/tests/test_processing_jobs.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/document_ingestion
git commit -m "feat: add document processing jobs"
```

---

### Task 4: Private Upload Registration Service

**Files:**
- Modify: `backend/document_ingestion/services.py`
- Create: `backend/document_ingestion/tests/test_private_uploads.py`

**Interfaces:**
- Consumes: `build_private_storage_key`, `DocumentVersion`, `DocumentAsset`, `ProcessingJob`, `enqueue_processing_job`.
- Produces: `register_private_upload(...) -> DocumentAsset`.

- [ ] **Step 1: Write failing private upload tests**

Create `backend/document_ingestion/tests/test_private_uploads.py`:

```python
import pytest
from django.contrib.auth import get_user_model

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob
from document_ingestion.services import register_private_upload


def create_document():
    domain = AcademicDomain.objects.create(name="Archives academiques", slug="archives-academiques")
    return Document.objects.create(
        title="Archives numeriques UOB",
        slug="archives-numeriques-uob",
        academic_domain=domain,
        category=Document.Category.INSTITUTIONAL_FUND,
        access_model=Document.AccessModel.PRIVATE,
    )


@pytest.mark.django_db
def test_register_private_upload_creates_version_asset_and_job(settings):
    settings.DOCUMENT_STORAGE_BUCKET = "bibliogabon-private-documents"
    User = get_user_model()
    user = User.objects.create_user(email="staff@example.ga", password="pass")
    document = create_document()

    asset = register_private_upload(
        document=document,
        storage_key="documents/1/versions/v1/abcdef12/source.pdf",
        original_filename="source.pdf",
        mime_type="application/pdf",
        byte_size=8192,
        checksum_sha256="e" * 64,
        uploaded_by=user,
        version_label="v1",
    )

    version = asset.version
    job = ProcessingJob.objects.get(version=version)

    assert version.document == document
    assert version.version_label == "v1"
    assert version.uploaded_by == user
    assert asset.asset_type == DocumentAsset.AssetType.SOURCE_PDF
    assert asset.storage_bucket == "bibliogabon-private-documents"
    assert job.status == ProcessingJob.Status.QUEUED
    assert job.source_asset == asset


@pytest.mark.django_db
def test_register_private_upload_is_idempotent_for_same_version_and_checksum(settings):
    settings.DOCUMENT_STORAGE_BUCKET = "bibliogabon-private-documents"
    document = create_document()

    first = register_private_upload(
        document=document,
        storage_key="documents/1/versions/v1/abcdef12/source.pdf",
        original_filename="source.pdf",
        mime_type="application/pdf",
        byte_size=8192,
        checksum_sha256="f" * 64,
        version_label="v1",
    )
    second = register_private_upload(
        document=document,
        storage_key="documents/1/versions/v1/abcdef12/source.pdf",
        original_filename="source.pdf",
        mime_type="application/pdf",
        byte_size=8192,
        checksum_sha256="f" * 64,
        version_label="v1",
    )

    assert first.pk == second.pk
    assert DocumentVersion.objects.count() == 1
    assert DocumentAsset.objects.count() == 1
    assert ProcessingJob.objects.count() == 1


@pytest.mark.parametrize("storage_key", ["http://example.com/source.pdf", "https://example.com/source.pdf", "file:///tmp/source.pdf"])
@pytest.mark.django_db
def test_register_private_upload_rejects_public_storage_reference(storage_key):
    with pytest.raises(ValueError):
        register_private_upload(
            document=create_document(),
            storage_key=storage_key,
            original_filename="source.pdf",
            mime_type="application/pdf",
            byte_size=8192,
            checksum_sha256="a" * 64,
            version_label="v1",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest document_ingestion/tests/test_private_uploads.py -q
```

Expected: FAIL because `register_private_upload()` does not exist.

- [ ] **Step 3: Implement upload service**

Append to `backend/document_ingestion/services.py`:

```python
from django.conf import settings

from document_ingestion.storage import storage_key_is_public_reference


def source_asset_type_for_mime_type(mime_type: str) -> str:
    if mime_type == "application/pdf":
        return DocumentAsset.AssetType.SOURCE_PDF
    if mime_type == "application/epub+zip":
        return DocumentAsset.AssetType.SOURCE_EPUB
    return DocumentAsset.AssetType.SOURCE_RAW


def register_private_upload(
    *,
    document,
    storage_key: str,
    original_filename: str,
    mime_type: str,
    byte_size: int,
    checksum_sha256: str,
    uploaded_by=None,
    version_label: str = "v1",
) -> DocumentAsset:
    if storage_key_is_public_reference(storage_key):
        raise ValueError("storage_key must be a private object key")

    version, _ = DocumentVersion.objects.get_or_create(
        document=document,
        version_label=version_label,
        defaults={"uploaded_by": uploaded_by},
    )
    asset, _ = DocumentAsset.objects.get_or_create(
        version=version,
        asset_type=source_asset_type_for_mime_type(mime_type),
        checksum_sha256=checksum_sha256,
        defaults={
            "storage_bucket": settings.DOCUMENT_STORAGE_BUCKET,
            "storage_key": storage_key,
            "mime_type": mime_type,
            "byte_size": byte_size,
        },
    )
    enqueue_processing_job(
        version=version,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key=f"ingest:{document.pk}:{version_label}:{checksum_sha256}",
        source_asset=asset,
        input_payload={"original_filename": original_filename},
    )
    return asset
```

- [ ] **Step 4: Run task tests**

Run:

```bash
cd backend
pytest document_ingestion/tests/test_private_uploads.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/document_ingestion
git commit -m "feat: register private document uploads"
```

---

### Task 5: Admin And Full Verification

**Files:**
- Create: `backend/document_ingestion/admin.py`
- Create: `backend/document_ingestion/tests/test_admin_registration.py`

**Interfaces:**
- Consumes: `DocumentVersion`, `DocumentAsset`, `ProcessingJob`.
- Produces: admin registration and final verification.

- [ ] **Step 1: Write failing admin registration test**

Create `backend/document_ingestion/tests/test_admin_registration.py`:

```python
from django.contrib import admin

from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob


def test_document_ingestion_models_are_registered_in_admin():
    assert DocumentVersion in admin.site._registry
    assert DocumentAsset in admin.site._registry
    assert ProcessingJob in admin.site._registry
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest document_ingestion/tests/test_admin_registration.py -q
```

Expected: FAIL because admin registrations do not exist.

- [ ] **Step 3: Register ingestion models**

Create `backend/document_ingestion/admin.py`:

```python
from django.contrib import admin

from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ["document", "version_label", "status", "is_current", "uploaded_by", "created_at"]
    list_filter = ["status", "is_current", "source_retention_policy"]
    search_fields = ["document__title", "version_label", "processing_summary"]
    autocomplete_fields = ["document", "uploaded_by"]
    readonly_fields = ["created_at", "updated_at", "processed_at"]


@admin.register(DocumentAsset)
class DocumentAssetAdmin(admin.ModelAdmin):
    list_display = ["version", "asset_type", "storage_bucket", "storage_key", "mime_type", "byte_size", "visibility"]
    list_filter = ["asset_type", "visibility", "mime_type"]
    search_fields = ["version__document__title", "storage_key", "checksum_sha256"]
    autocomplete_fields = ["version", "created_by_job"]
    readonly_fields = ["created_at"]


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ["job_type", "version", "status", "retry_count", "idempotency_key", "created_at"]
    list_filter = ["job_type", "status"]
    search_fields = ["version__document__title", "idempotency_key", "celery_task_id", "error_code"]
    autocomplete_fields = ["version", "source_asset"]
    readonly_fields = ["created_at", "updated_at", "started_at", "completed_at", "failed_at"]
```

- [ ] **Step 4: Run ingestion tests**

Run:

```bash
cd backend
pytest document_ingestion/tests -q
```

Expected: PASS.

- [ ] **Step 5: Run full backend verification**

Run:

```bash
cd backend
pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
```

Expected: tests pass, system checks pass, no missing migrations, all migrations apply.

- [ ] **Step 6: Commit**

```bash
git add backend/document_ingestion backend/config/settings.py backend/pytest.ini backend/pyproject.toml
git commit -m "feat: expose document ingestion in admin"
```

---

## Self-Review Checklist

- [ ] `document_ingestion` is separate from `catalog`.
- [ ] `catalog` does not import `document_ingestion`.
- [ ] Raw file references are stored as private bucket/key metadata only.
- [ ] No public URL or signed URL behavior is implemented.
- [ ] Document versions are unique per document and label.
- [ ] Asset registration is idempotent by version, asset type, and checksum.
- [ ] Processing jobs are idempotent by key and record retry/error state.
- [ ] `register_private_upload()` creates a version, source asset, and queued processing job.
- [ ] No OCR, page rendering, search, reader, billing, or Celery worker code is added.
- [ ] Full tests, Django checks, migration check, and migrations pass.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-27-bibliogabon-document-ingestion.md`.

Recommended execution: sequential TDD in this session, with sub-agent code review after implementation. The tasks share model files, so parallel implementation agents should not edit the same app concurrently.
