from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class DocumentPage(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    version = models.ForeignKey(
        "document_ingestion.DocumentVersion",
        on_delete=models.CASCADE,
        related_name="pages",
    )
    page_number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_by_job = models.ForeignKey(
        "document_ingestion.ProcessingJob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_pages",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "page_number"],
                name="uniq_page_number_per_document_version",
            ),
            models.CheckConstraint(
                condition=Q(page_number__gte=1),
                name="document_page_number_positive",
            ),
        ]
        ordering = ["version", "page_number"]

    def clean(self):
        if self.created_by_job_id and self.created_by_job.version_id != self.version_id:
            raise ValidationError("Processing job must belong to the same document version")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.version} page {self.page_number}"


class ExtractedText(models.Model):
    class ExtractionMethod(models.TextChoices):
        TEXT_LAYER = "text_layer", "Text layer"
        OCR = "ocr", "OCR"
        MANUAL = "manual", "Manual"

    page = models.OneToOneField(
        DocumentPage,
        on_delete=models.CASCADE,
        related_name="extracted_text",
    )
    text = models.TextField()
    language_code = models.CharField(max_length=12, default="fr")
    extraction_method = models.CharField(
        max_length=24,
        choices=ExtractionMethod.choices,
        default=ExtractionMethod.TEXT_LAYER,
    )
    confidence = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    created_by_job = models.ForeignKey(
        "document_ingestion.ProcessingJob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_extracted_texts",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page"]

    def clean(self):
        if not self.text or not self.text.strip():
            raise ValidationError("Extracted text must not be blank")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValidationError("Confidence must be between 0 and 1")
        if self.created_by_job_id and self.created_by_job.version_id != self.page.version_id:
            raise ValidationError("Processing job must belong to the same document version")

    def save(self, *args, **kwargs):
        if self.confidence is not None:
            self.confidence = Decimal(str(self.confidence))
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Text for {self.page}"


class SearchIndexRecord(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        INDEXED = "indexed", "Indexed"
        FAILED = "failed", "Failed"

    page = models.OneToOneField(
        DocumentPage,
        on_delete=models.CASCADE,
        related_name="search_index_record",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    content_hash = models.CharField(
        max_length=64,
        validators=[
            RegexValidator(
                regex=r"^[a-f0-9]{64}$",
                message="Content hash must be a lowercase SHA-256 hex digest",
            )
        ],
    )
    language_code = models.CharField(max_length=12, default="fr")
    indexed_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"], name="search_index_status_idx"),
            models.Index(fields=["language_code"], name="search_index_language_idx"),
        ]
        ordering = ["page"]

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.status}: {self.page}"
