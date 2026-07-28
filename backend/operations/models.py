from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class AuditLogQuerySet(models.QuerySet):
    def delete(self, *args, **kwargs):
        raise ValueError("Audit logs are immutable")


class AuditLogManager(models.Manager.from_queryset(AuditLogQuerySet)):
    pass


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operations_audit_logs",
    )
    event_type = models.CharField(max_length=80, db_index=True)
    target_app = models.CharField(max_length=80, blank=True)
    target_model = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=80, blank=True)
    summary = models.CharField(max_length=240)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    objects = AuditLogManager()

    class Meta:
        base_manager_name = "objects"
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["target_app", "target_model", "target_id"]),
            models.Index(fields=["actor", "created_at"]),
        ]
        ordering = ["-created_at"]

    def clean(self):
        if not self.event_type.strip():
            raise ValidationError("event_type is required")
        if not self.summary.strip():
            raise ValidationError("summary is required")
        if not isinstance(self.metadata, dict):
            raise ValidationError("metadata must be a JSON object")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Audit logs are immutable")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit logs are immutable")

    def __str__(self) -> str:
        return f"{self.event_type}: {self.summary}"


class PublicationReview(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    document = models.ForeignKey("catalog.Document", on_delete=models.PROTECT, related_name="publication_reviews")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opened_publication_reviews",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_publication_reviews",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_publication_reviews",
    )
    decision_reason = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    opened_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["document", "status"]),
            models.Index(fields=["status", "opened_at"]),
            models.Index(fields=["reviewer", "status"]),
        ]
        ordering = ["-opened_at", "-created_at"]

    def clean(self):
        if self.status == self.Status.OPEN and self.decided_at is not None:
            raise ValidationError("open reviews cannot have decided_at")
        if self.status in {self.Status.APPROVED, self.Status.REJECTED, self.Status.CANCELLED}:
            if self.decided_at is None:
                raise ValidationError("closed reviews require decided_at")
        if self.status == self.Status.REJECTED and not self.decision_reason.strip():
            raise ValidationError("rejected reviews require decision_reason")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.document}: {self.status}"


class SupportTicket(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING = "waiting", "Waiting"
        RESOLVED = "resolved", "Resolved"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=180)
    description = models.TextField()
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_support_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_support_tickets",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operations_support_tickets",
    )
    organization = models.ForeignKey(
        "accounts.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_tickets",
    )
    document = models.ForeignKey(
        "catalog.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_tickets",
    )
    payment_transaction = models.ForeignKey(
        "billing.PaymentTransaction",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_tickets",
    )
    entitlement = models.ForeignKey(
        "accounts.Entitlement",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_tickets",
    )
    resolution_summary = models.TextField(blank=True)
    opened_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["opened_at"]),
        ]
        ordering = ["-opened_at", "-created_at"]

    def clean(self):
        if not self.title.strip():
            raise ValidationError("title is required")
        if not self.description.strip():
            raise ValidationError("description is required")
        if self.status in {self.Status.RESOLVED, self.Status.CANCELLED}:
            if self.resolved_at is None:
                raise ValidationError("closed tickets require resolved_at")
        if self.status == self.Status.RESOLVED and not self.resolution_summary.strip():
            raise ValidationError("resolved tickets require resolution_summary")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"
