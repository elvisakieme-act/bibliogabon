from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from catalog.models import Document


class DailyUsageAggregate(models.Model):
    date = models.DateField()
    organization = models.ForeignKey(
        "accounts.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="daily_usage_aggregates",
    )
    document = models.ForeignKey(
        "catalog.Document",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="daily_usage_aggregates",
    )
    academic_domain = models.ForeignKey(
        "catalog.AcademicDomain",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="daily_usage_aggregates",
    )
    access_model = models.CharField(max_length=24, choices=Document.AccessModel.choices)
    reader_session_count = models.PositiveIntegerField(default=0)
    page_view_count = models.PositiveIntegerField(default=0)
    distinct_document_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["date", "organization", "document", "academic_domain", "access_model"],
                name="uniq_daily_usage_aggregate_dim",
                nulls_distinct=False,
            )
        ]
        indexes = [
            models.Index(fields=["date", "organization"], name="daily_usage_date_org_idx"),
            models.Index(fields=["document", "date"], name="daily_usage_doc_date_idx"),
        ]
        ordering = ["-date", "organization__name", "document__title"]

    def clean(self):
        if (
            self.document_id
            and self.academic_domain_id
            and self.document.academic_domain_id != self.academic_domain_id
        ):
            raise ValidationError("academic_domain must match the document domain")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class InstitutionReport(models.Model):
    class Status(models.TextChoices):
        GENERATED = "generated", "Generated"
        FAILED = "failed", "Failed"

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="institution_reports",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.GENERATED)
    metrics = models.JSONField(default=dict, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_institution_reports",
    )
    generated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "period_start", "period_end"],
                name="uniq_institution_report_period",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "period_start", "period_end"],
                name="institution_report_period_idx",
            ),
            models.Index(fields=["status", "generated_at"], name="institution_report_status_idx"),
        ]
        ordering = ["organization__name", "-period_end"]

    def clean(self):
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValidationError("period_start must be on or before period_end")
        if not isinstance(self.metrics, dict):
            raise ValidationError("metrics must be a JSON object")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class AnalyticsRun(models.Model):
    class RunType(models.TextChoices):
        DAILY_USAGE_AGGREGATE = "daily_usage_aggregate", "Daily usage aggregate"
        INSTITUTION_REPORT = "institution_report", "Institution report"

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    run_type = models.CharField(max_length=32, choices=RunType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    organization = models.ForeignKey(
        "accounts.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analytics_runs",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["run_type", "status"], name="analytics_run_type_status_idx"),
            models.Index(fields=["period_start", "period_end"], name="analytics_run_period_idx"),
        ]
        ordering = ["-started_at"]

    def clean(self):
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValidationError("period_start must be on or before period_end")
        if not isinstance(self.metadata, dict):
            raise ValidationError("metadata must be a JSON object")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
