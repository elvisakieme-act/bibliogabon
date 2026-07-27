from __future__ import annotations

from django.core.exceptions import ValidationError
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
