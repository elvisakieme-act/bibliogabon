from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ReaderSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    session_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reader_sessions",
    )
    document = models.ForeignKey(
        "catalog.Document",
        on_delete=models.PROTECT,
        related_name="reader_sessions",
    )
    version = models.ForeignKey(
        "document_ingestion.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="reader_sessions",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    client_ip = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"], name="reader_session_user_status_idx"),
            models.Index(fields=["document", "status"], name="reader_session_doc_status_idx"),
            models.Index(fields=["expires_at"], name="reader_session_expires_idx"),
        ]
        ordering = ["-started_at", "-created_at"]

    def clean(self):
        if self.version_id and self.document_id and self.version.document_id != self.document_id:
            raise ValidationError("Reader session version must belong to the same document")
        if (
            self.status == self.Status.ACTIVE
            and self.expires_at is not None
            and self.started_at is not None
            and self.expires_at <= self.started_at
        ):
            raise ValidationError("Active reader sessions must expire after they start")
        if self.status == self.Status.ENDED and self.ended_at is None:
            raise ValidationError("Ended reader sessions must record ended_at")

    def is_active_at(self, at=None) -> bool:
        at = at or timezone.now()
        return self.status == self.Status.ACTIVE and self.ended_at is None and self.expires_at > at

    def end(self, at=None):
        at = at or timezone.now()
        self.status = self.Status.ENDED
        self.ended_at = at
        self.last_seen_at = at
        self.save(update_fields=["status", "ended_at", "last_seen_at", "updated_at"])
        return self

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user} reading {self.document}"


class PageAccessLog(models.Model):
    session = models.ForeignKey(
        ReaderSession,
        on_delete=models.CASCADE,
        related_name="page_access_logs",
    )
    page = models.ForeignKey(
        "document_processing.DocumentPage",
        on_delete=models.PROTECT,
        related_name="access_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="page_access_logs",
    )
    document = models.ForeignKey(
        "catalog.Document",
        on_delete=models.PROTECT,
        related_name="page_access_logs",
    )
    page_number = models.PositiveIntegerField()
    accessed_at = models.DateTimeField(default=timezone.now)
    client_ip = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(page_number__gte=1),
                name="page_access_log_page_number_positive",
            )
        ]
        indexes = [
            models.Index(fields=["user", "accessed_at"], name="page_access_user_time_idx"),
            models.Index(fields=["document", "accessed_at"], name="page_access_doc_time_idx"),
        ]
        ordering = ["-accessed_at"]

    def clean(self):
        if self.user_id and self.session_id and self.user_id != self.session.user_id:
            raise ValidationError("Page access user must match the reader session user")
        if self.document_id and self.session_id and self.document_id != self.session.document_id:
            raise ValidationError("Page access document must match the reader session document")
        if self.page_id and self.session_id and self.page.version_id != self.session.version_id:
            raise ValidationError("Page access page must belong to the session version")
        if self.page_id and self.page_number != self.page.page_number:
            raise ValidationError("Page access page_number must match the page")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user} read {self.document} page {self.page_number}"
