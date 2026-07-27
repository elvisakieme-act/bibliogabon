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

    document = models.ForeignKey(
        "catalog.Document",
        on_delete=models.CASCADE,
        related_name="versions",
    )
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
            models.UniqueConstraint(
                fields=["document", "version_label"],
                name="uniq_version_label_per_document",
            )
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
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )
    created_by_job = models.ForeignKey(
        "ProcessingJob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_assets",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "asset_type", "checksum_sha256"],
                name="uniq_asset_checksum_per_version_type",
            ),
            models.CheckConstraint(
                condition=~models.Q(storage_key__contains="://")
                & ~models.Q(storage_key__startswith="//")
                & ~models.Q(storage_key__contains=".."),
                name="document_asset_storage_key_not_public_scheme",
            ),
        ]
        ordering = ["version", "asset_type", "created_at"]

    def clean(self):
        if storage_key_is_public_reference(self.storage_key):
            raise ValidationError("Storage key must be a private object key, not a public reference")
        source_types = {
            self.AssetType.SOURCE_RAW,
            self.AssetType.SOURCE_PDF,
            self.AssetType.SOURCE_EPUB,
        }
        if self.asset_type in source_types and self.visibility != self.Visibility.PRIVATE:
            raise ValidationError("Source assets must remain private")

    def __str__(self) -> str:
        return f"{self.asset_type}: {self.storage_key}"

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


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

    version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name="processing_jobs",
    )
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

    def clean(self):
        if self.source_asset_id and self.source_asset.version_id != self.version_id:
            raise ValidationError("Source asset must belong to the same document version")

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
        self.save(
            update_fields=[
                "status",
                "retry_count",
                "error_code",
                "error_message",
                "failed_at",
                "updated_at",
            ]
        )

    def mark_completed(self, *, output_asset_ids=None):
        self.status = self.Status.SUCCEEDED
        self.output_asset_ids = output_asset_ids or []
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "output_asset_ids", "completed_at", "updated_at"])

    def __str__(self) -> str:
        return f"{self.job_type} for {self.version}"

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
