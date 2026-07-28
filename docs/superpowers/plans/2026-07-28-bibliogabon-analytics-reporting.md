# BiblioGABON Analytics Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend analytics foundation for privacy-conscious institutional reports.

**Architecture:** Create a Django app named `analytics` with aggregate models and report-generation services. Reader logs remain the operational source, while analytics persists only daily aggregates and generated organization report snapshots.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, pytest, pytest-django, SQLite local/test fallback, PostgreSQL production compatibility.

## Global Constraints

- Organization-scoped reports must avoid unnecessary personal reading data.
- Reports must not expose user emails, user IDs, reader session keys, IP addresses, user agents, individual page paths, or per-reader history.
- Organization attribution is conservative: count reading activity for an organization only when the user had exactly one active organization membership at the activity timestamp.
- Aggregates are idempotent for the same date and dimensional keys.
- Report generation is synchronous in this slice.
- Generated reports may include catalog metadata such as document titles and academic domain names.
- Do not implement a custom frontend dashboard, exports, raw search-query analytics, per-user reading history, exact entitlement-source attribution, streaming analytics, external BI providers, forecasting, recommendations, or machine learning.

---

## File Structure

```text
backend/
  analytics/
    __init__.py
    admin.py
    apps.py
    models.py
    services.py
    migrations/
      __init__.py
    tests/
      __init__.py
      factories.py
      test_admin_registration.py
      test_bootstrap.py
      test_institution_reports.py
      test_models.py
      test_usage_aggregates.py
  config/
    settings.py
  pyproject.toml
  pytest.ini
```

---

### Task 1: Analytics App Scaffold

**Files:**
- Create: `backend/analytics/__init__.py`
- Create: `backend/analytics/apps.py`
- Create: `backend/analytics/migrations/__init__.py`
- Create: `backend/analytics/tests/__init__.py`
- Create: `backend/analytics/tests/test_bootstrap.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/pytest.ini`

**Interfaces:**
- Produces installed Django app `analytics`.
- Produces `AnalyticsConfig` with `name = "analytics"`.

- [ ] **Step 1: Write the failing bootstrap test**

```python
from django.apps import apps


def test_analytics_app_is_installed():
    assert apps.is_installed("analytics")
```

- [ ] **Step 2: Run test to verify it fails**

Run from `backend`: `python -m pytest analytics/tests/test_bootstrap.py -q`

Expected: FAIL because the `analytics` app is not installed.

- [ ] **Step 3: Add app scaffold**

Create `backend/analytics/apps.py`:

```python
from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "analytics"
```

- [ ] **Step 4: Register app and tests**

Add `"analytics"` after `"operations"` in `INSTALLED_APPS`.

Add `analytics/tests` to `testpaths` in both `backend/pyproject.toml` and `backend/pytest.ini`.

- [ ] **Step 5: Run test to verify it passes**

Run from `backend`: `python -m pytest analytics/tests/test_bootstrap.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/analytics backend/config/settings.py backend/pyproject.toml backend/pytest.ini
git commit -m "feat: add analytics app scaffold"
```

---

### Task 2: Analytics Domain Models

**Files:**
- Create: `backend/analytics/models.py`
- Create: `backend/analytics/tests/test_models.py`
- Generate: `backend/analytics/migrations/0001_initial.py`

**Interfaces:**
- Produces `DailyUsageAggregate`.
- Produces `InstitutionReport`.
- Produces `AnalyticsRun`.

- [ ] **Step 1: Write failing model tests**

Create `backend/analytics/tests/test_models.py`:

```python
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Organization
from analytics.models import AnalyticsRun, DailyUsageAggregate, InstitutionReport
from catalog.models import AcademicDomain, Document


@pytest.mark.django_db
def test_daily_usage_aggregate_stores_aggregate_dimensions():
    organization = Organization.objects.create(name="UOB", slug="uob")
    domain = AcademicDomain.objects.create(name="Droit", slug="droit")
    document = Document.objects.create(
        title="Droit administratif",
        slug="droit-administratif",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )

    aggregate = DailyUsageAggregate.objects.create(
        date=timezone.datetime(2026, 1, 15).date(),
        organization=organization,
        document=document,
        academic_domain=domain,
        access_model=document.access_model,
        reader_session_count=2,
        page_view_count=9,
        distinct_document_count=1,
    )

    assert aggregate.organization == organization
    assert aggregate.document == document
    assert aggregate.academic_domain == domain
    assert aggregate.reader_session_count == 2
    assert aggregate.page_view_count == 9
    assert aggregate.distinct_document_count == 1


@pytest.mark.django_db
def test_institution_report_rejects_inverted_period():
    organization = Organization.objects.create(name="USTM", slug="ustm")
    report = InstitutionReport(
        organization=organization,
        period_start=timezone.datetime(2026, 1, 31).date(),
        period_end=timezone.datetime(2026, 1, 1).date(),
        metrics={},
    )

    with pytest.raises(ValidationError):
        report.save()


@pytest.mark.django_db
def test_analytics_run_rejects_non_object_metadata():
    run = AnalyticsRun(
        run_type=AnalyticsRun.RunType.INSTITUTION_REPORT,
        period_start=timezone.datetime(2026, 1, 1).date(),
        period_end=timezone.datetime(2026, 1, 31).date(),
        metadata=[],
    )

    with pytest.raises(ValidationError):
        run.save()
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `python -m pytest analytics/tests/test_models.py -q`

Expected: FAIL because `analytics.models` does not exist.

- [ ] **Step 3: Implement models**

Create `backend/analytics/models.py` with:

```python
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
            )
        ]
        indexes = [
            models.Index(fields=["date", "organization"], name="daily_usage_date_org_idx"),
            models.Index(fields=["document", "date"], name="daily_usage_doc_date_idx"),
        ]
        ordering = ["-date", "organization__name", "document__title"]

    def clean(self):
        if self.document_id and self.academic_domain_id and self.document.academic_domain_id != self.academic_domain_id:
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
            models.Index(fields=["organization", "period_start", "period_end"], name="institution_report_period_idx"),
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
```

- [ ] **Step 4: Generate migration**

Run from `backend`: `python manage.py makemigrations analytics`

Expected: migration `analytics/migrations/0001_initial.py` is created.

- [ ] **Step 5: Run tests to verify they pass**

Run from `backend`: `python -m pytest analytics/tests/test_models.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/analytics
git commit -m "feat: add analytics domain models"
```

---

### Task 3: Daily Usage Aggregation

**Files:**
- Create: `backend/analytics/services.py`
- Create: `backend/analytics/tests/factories.py`
- Create: `backend/analytics/tests/test_usage_aggregates.py`

**Interfaces:**
- Produces `build_daily_usage_aggregate(day) -> list[DailyUsageAggregate]`.
- Produces internal helper `_single_active_organization_for_user_at(user, at)`.

- [ ] **Step 1: Add analytics test factories**

Create `backend/analytics/tests/factories.py` with helpers that create real Django model rows:

```python
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Organization, OrganizationMembership
from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_reader.models import PageAccessLog, ReaderSession


def create_user(email="analytics-reader@example.ga"):
    return get_user_model().objects.create_user(email=email, password="pass")


def create_organization(slug="analytics-org"):
    return Organization.objects.create(name=f"Organization {slug}", slug=slug)


def create_active_membership(user, organization, *, starts_at=None, ends_at=None):
    return OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        status=OrganizationMembership.Status.ACTIVE,
        starts_at=starts_at or timezone.now() - timezone.timedelta(days=1),
        ends_at=ends_at,
    )


def create_document(slug="analytics-document", access_model=Document.AccessModel.FREE):
    domain = AcademicDomain.objects.create(name=f"Domain {slug}", slug=f"domain-{slug}")
    return Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )


def create_reader_activity(*, user, document, started_at, page_views=1):
    version = DocumentVersion.objects.create(
        document=document,
        version_label=f"v-{document.pk}-{started_at.strftime('%Y%m%d%H%M%S')}",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=max(page_views, 1),
    )
    session = ReaderSession.objects.create(
        user=user,
        document=document,
        version=version,
        started_at=started_at,
        expires_at=started_at + timezone.timedelta(hours=2),
        last_seen_at=started_at,
        client_ip="196.223.12.10",
        user_agent="BiblioGABON test client",
    )
    for page_number in range(1, page_views + 1):
        page = DocumentPage.objects.create(
            version=version,
            page_number=page_number,
            status=DocumentPage.Status.PROCESSED,
        )
        PageAccessLog.objects.create(
            session=session,
            page=page,
            user=user,
            document=document,
            page_number=page_number,
            accessed_at=started_at + timezone.timedelta(minutes=page_number),
            client_ip=session.client_ip,
            user_agent=session.user_agent,
        )
    return session
```

- [ ] **Step 2: Write failing aggregation tests**

Create `backend/analytics/tests/test_usage_aggregates.py`:

```python
import pytest
from django.utils import timezone

from analytics.models import DailyUsageAggregate
from analytics.services import build_daily_usage_aggregate
from analytics.tests.factories import (
    create_active_membership,
    create_document,
    create_organization,
    create_reader_activity,
    create_user,
)


@pytest.mark.django_db
def test_daily_usage_aggregate_counts_single_organization_activity():
    at = timezone.make_aware(timezone.datetime(2026, 1, 15, 10, 0, 0))
    user = create_user()
    organization = create_organization(slug="uob")
    create_active_membership(user, organization, starts_at=at - timezone.timedelta(days=1))
    document = create_document(slug="macro", access_model="subscription")
    create_reader_activity(user=user, document=document, started_at=at, page_views=2)

    aggregates = build_daily_usage_aggregate(at.date())

    assert len(aggregates) == 1
    aggregate = DailyUsageAggregate.objects.get()
    assert aggregate.organization == organization
    assert aggregate.document == document
    assert aggregate.academic_domain == document.academic_domain
    assert aggregate.access_model == document.access_model
    assert aggregate.reader_session_count == 1
    assert aggregate.page_view_count == 2
    assert aggregate.distinct_document_count == 1


@pytest.mark.django_db
def test_daily_usage_aggregate_rebuild_updates_existing_row():
    at = timezone.make_aware(timezone.datetime(2026, 1, 15, 10, 0, 0))
    user = create_user(email="repeat@example.ga")
    organization = create_organization(slug="ustm")
    create_active_membership(user, organization, starts_at=at - timezone.timedelta(days=1))
    document = create_document(slug="math")
    create_reader_activity(user=user, document=document, started_at=at, page_views=1)

    first = build_daily_usage_aggregate(at.date())[0]
    create_reader_activity(user=user, document=document, started_at=at + timezone.timedelta(hours=1), page_views=2)
    second = build_daily_usage_aggregate(at.date())[0]

    assert first.pk == second.pk
    assert DailyUsageAggregate.objects.count() == 1
    assert second.reader_session_count == 2
    assert second.page_view_count == 3


@pytest.mark.django_db
def test_daily_usage_aggregate_excludes_ambiguous_multi_organization_activity():
    at = timezone.make_aware(timezone.datetime(2026, 1, 15, 10, 0, 0))
    user = create_user(email="multi@example.ga")
    first_org = create_organization(slug="org-a")
    second_org = create_organization(slug="org-b")
    create_active_membership(user, first_org, starts_at=at - timezone.timedelta(days=1))
    create_active_membership(user, second_org, starts_at=at - timezone.timedelta(days=1))
    document = create_document(slug="ambiguous")
    create_reader_activity(user=user, document=document, started_at=at, page_views=1)

    aggregates = build_daily_usage_aggregate(at.date())

    assert aggregates == []
    assert DailyUsageAggregate.objects.count() == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run from `backend`: `python -m pytest analytics/tests/test_usage_aggregates.py -q`

Expected: FAIL because `build_daily_usage_aggregate` is not implemented.

- [ ] **Step 4: Implement aggregation service**

Create `backend/analytics/services.py` with:

```python
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Organization, OrganizationMembership
from analytics.models import AnalyticsRun, DailyUsageAggregate
from document_reader.models import PageAccessLog, ReaderSession


def _day_bounds(day):
    start = timezone.make_aware(datetime.combine(day, time.min))
    return start, start + timezone.timedelta(days=1)


def _single_active_organization_for_user_at(user, at):
    organization_ids = list(
        OrganizationMembership.objects.filter(
            user=user,
            status=OrganizationMembership.Status.ACTIVE,
            starts_at__lte=at,
            organization__status=Organization.Status.ACTIVE,
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))
        .values_list("organization_id", flat=True)
        .distinct()
    )
    if len(organization_ids) != 1:
        return None
    return Organization.objects.get(pk=organization_ids[0])


def _dimension_for_activity(*, user, document, at):
    organization = _single_active_organization_for_user_at(user, at)
    if organization is None:
        return None
    return (
        organization.pk,
        document.pk,
        document.academic_domain_id,
        document.access_model,
    )


def build_daily_usage_aggregate(day) -> list[DailyUsageAggregate]:
    start, end = _day_bounds(day)
    run = AnalyticsRun.objects.create(
        run_type=AnalyticsRun.RunType.DAILY_USAGE_AGGREGATE,
        period_start=day,
        period_end=day,
        metadata={"date": day.isoformat()},
    )
    counters = defaultdict(lambda: {"reader_session_count": 0, "page_view_count": 0})

    try:
        sessions = ReaderSession.objects.filter(started_at__gte=start, started_at__lt=end).select_related(
            "user",
            "document",
            "document__academic_domain",
        )
        for session in sessions:
            key = _dimension_for_activity(user=session.user, document=session.document, at=session.started_at)
            if key is not None:
                counters[key]["reader_session_count"] += 1

        page_logs = PageAccessLog.objects.filter(accessed_at__gte=start, accessed_at__lt=end).select_related(
            "user",
            "document",
            "document__academic_domain",
        )
        for log in page_logs:
            key = _dimension_for_activity(user=log.user, document=log.document, at=log.accessed_at)
            if key is not None:
                counters[key]["page_view_count"] += 1

        aggregates = []
        with transaction.atomic():
            for (organization_id, document_id, domain_id, access_model), values in counters.items():
                aggregate, _ = DailyUsageAggregate.objects.update_or_create(
                    date=day,
                    organization_id=organization_id,
                    document_id=document_id,
                    academic_domain_id=domain_id,
                    access_model=access_model,
                    defaults={
                        "reader_session_count": values["reader_session_count"],
                        "page_view_count": values["page_view_count"],
                        "distinct_document_count": 1,
                    },
                )
                aggregates.append(aggregate)

        run.status = AnalyticsRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])
        return aggregates
    except Exception as exc:
        run.status = AnalyticsRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)
        run.save(update_fields=["status", "finished_at", "error_message"])
        raise
```

- [ ] **Step 5: Run tests to verify they pass**

Run from `backend`: `python -m pytest analytics/tests/test_usage_aggregates.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/analytics
git commit -m "feat: aggregate institutional reader usage"
```

---

### Task 4: Institution Report Generation

**Files:**
- Modify: `backend/analytics/services.py`
- Create: `backend/analytics/tests/test_institution_reports.py`

**Interfaces:**
- Produces `generate_institution_report(organization, period_start, period_end, generated_by=None) -> InstitutionReport`.
- Produces `serialize_institution_report(report) -> dict`.

- [ ] **Step 1: Write failing report tests**

Create `backend/analytics/tests/test_institution_reports.py`:

```python
import pytest
from django.utils import timezone

from accounts.models import Entitlement
from analytics.models import InstitutionReport
from analytics.services import generate_institution_report, serialize_institution_report
from analytics.tests.factories import (
    create_active_membership,
    create_document,
    create_organization,
    create_reader_activity,
    create_user,
)
from billing.models import CommercialOffer, OrganizationQuota, PaymentTransaction, Subscription
from operations.models import AuditLog, SupportTicket


def _forbidden_keys(payload):
    forbidden = {"email", "user_id", "user_ids", "session_key", "client_ip", "user_agent", "page_number"}
    found = set()

    def walk(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in forbidden:
                    found.add(key)
                walk(nested)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return found


@pytest.mark.django_db
def test_generate_institution_report_builds_private_organization_metrics():
    start = timezone.make_aware(timezone.datetime(2026, 1, 1, 9, 0, 0))
    end_date = timezone.datetime(2026, 1, 31).date()
    organization = create_organization(slug="report-org")
    user = create_user(email="report-reader@example.ga")
    create_active_membership(user, organization, starts_at=start - timezone.timedelta(days=1))
    document = create_document(slug="report-doc", access_model="subscription")
    create_reader_activity(user=user, document=document, started_at=start, page_views=3)
    Entitlement.objects.create(
        organization=organization,
        source=Entitlement.Source.ORGANIZATION_QUOTA,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=start - timezone.timedelta(days=1),
    )
    offer = CommercialOffer.objects.create(
        name="Institution annual",
        slug="institution-annual",
        offer_type=CommercialOffer.OfferType.ORGANIZATION,
        billing_period=CommercialOffer.BillingPeriod.ANNUAL,
        price_xaf=100000,
        duration_days=365,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
    )
    Subscription.objects.create(
        offer=offer,
        organization=organization,
        status=Subscription.Status.ACTIVE,
        starts_at=start - timezone.timedelta(days=1),
        ends_at=start + timezone.timedelta(days=365),
    )
    OrganizationQuota.objects.create(
        organization=organization,
        offer=offer,
        status=OrganizationQuota.Status.ACTIVE,
        seat_limit=50,
        starts_at=start - timezone.timedelta(days=1),
        ends_at=start + timezone.timedelta(days=365),
    )
    PaymentTransaction.objects.create(
        organization=organization,
        offer=offer,
        provider=PaymentTransaction.Provider.MANUAL_INVOICE,
        status=PaymentTransaction.Status.SUCCEEDED,
        amount_xaf=100000,
        idempotency_key="report-payment",
        succeeded_at=start,
    )
    SupportTicket.objects.create(
        title="Acces institution",
        description="Verification du contrat",
        organization=organization,
        opened_at=start,
    )

    report = generate_institution_report(organization, start.date(), end_date, generated_by=user)

    assert report.organization == organization
    assert report.period_start == start.date()
    assert report.period_end == end_date
    assert report.metrics["access"]["active_member_count"] == 1
    assert report.metrics["access"]["entitlements"]["active"] == 1
    assert report.metrics["access"]["quotas"]["active_count"] == 1
    assert report.metrics["access"]["quotas"]["seat_limit_total"] == 50
    assert report.metrics["access"]["subscriptions"]["active_count"] == 1
    assert report.metrics["commercial"]["payments"]["succeeded_amount_xaf"] == 100000
    assert report.metrics["support"]["opened_count"] == 1
    assert report.metrics["usage"]["reader_session_count"] == 1
    assert report.metrics["usage"]["page_view_count"] == 3
    assert report.metrics["usage"]["by_document"][0]["document_title"] == document.title
    assert AuditLog.objects.filter(event_type="institution_report_generated", target_id=str(report.pk)).exists()


@pytest.mark.django_db
def test_generate_institution_report_is_idempotent_for_same_period():
    start = timezone.datetime(2026, 1, 1).date()
    end = timezone.datetime(2026, 1, 31).date()
    organization = create_organization(slug="idempotent-report-org")

    first = generate_institution_report(organization, start, end)
    second = generate_institution_report(organization, start, end)

    assert first.pk == second.pk
    assert InstitutionReport.objects.count() == 1


@pytest.mark.django_db
def test_serialized_institution_report_excludes_personal_reader_data():
    start = timezone.datetime(2026, 1, 1).date()
    end = timezone.datetime(2026, 1, 31).date()
    organization = create_organization(slug="private-report-org")
    report = generate_institution_report(organization, start, end)

    payload = serialize_institution_report(report)

    assert _forbidden_keys(payload) == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `python -m pytest analytics/tests/test_institution_reports.py -q`

Expected: FAIL because report services are not implemented.

- [ ] **Step 3: Implement report services**

Extend `backend/analytics/services.py` with:

```python
def generate_institution_report(organization, period_start, period_end, generated_by=None):
    if period_start > period_end:
        raise ValueError("period_start must be on or before period_end")
    run = AnalyticsRun.objects.create(
        run_type=AnalyticsRun.RunType.INSTITUTION_REPORT,
        organization=organization,
        period_start=period_start,
        period_end=period_end,
        metadata={"organization_id": organization.pk},
    )
    try:
        current_day = period_start
        while current_day <= period_end:
            build_daily_usage_aggregate(current_day)
            current_day = current_day + timezone.timedelta(days=1)

        metrics = _build_institution_metrics(organization, period_start, period_end)
        report, _ = InstitutionReport.objects.update_or_create(
            organization=organization,
            period_start=period_start,
            period_end=period_end,
            defaults={
                "status": InstitutionReport.Status.GENERATED,
                "metrics": metrics,
                "generated_by": generated_by,
                "generated_at": timezone.now(),
            },
        )
        record_audit_event(
            actor=generated_by,
            event_type="institution_report_generated",
            target=report,
            summary=f"Institution report generated for {organization.name}",
            metadata={
                "organization_id": organization.pk,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "report_id": report.pk,
            },
        )
        run.status = AnalyticsRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.metadata = {"organization_id": organization.pk, "report_id": report.pk}
        run.save(update_fields=["status", "finished_at", "metadata"])
        return report
    except Exception as exc:
        run.status = AnalyticsRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)
        run.save(update_fields=["status", "finished_at", "error_message"])
        raise
```

Also add private helpers `_period_bounds`, `_sum_amount`, `_build_institution_metrics`, `_usage_by_day`, `_usage_by_domain`, `_usage_by_document`, and `_usage_by_access_model`. These helpers must use only organization-level querysets and aggregate rows.

`serialize_institution_report(report)` must return:

```python
{
    "id": report.pk,
    "organization": {
        "id": report.organization_id,
        "name": report.organization.name,
        "slug": report.organization.slug,
    },
    "period": {
        "start": report.period_start.isoformat(),
        "end": report.period_end.isoformat(),
    },
    "status": report.status,
    "metrics": report.metrics,
    "generated_at": report.generated_at.isoformat(),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run from `backend`: `python -m pytest analytics/tests/test_institution_reports.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/analytics
git commit -m "feat: generate institution analytics reports"
```

---

### Task 5: Admin Registration And Final Verification

**Files:**
- Create: `backend/analytics/admin.py`
- Create: `backend/analytics/tests/test_admin_registration.py`

**Interfaces:**
- Registers `DailyUsageAggregate`, `InstitutionReport`, and `AnalyticsRun` in Django Admin.
- Admin surfaces are read-only in this slice.

- [ ] **Step 1: Write failing admin tests**

Create `backend/analytics/tests/test_admin_registration.py`:

```python
import pytest
from django.contrib import admin
from django.test import RequestFactory

from analytics.admin import AnalyticsRunAdmin, DailyUsageAggregateAdmin, InstitutionReportAdmin
from analytics.models import AnalyticsRun, DailyUsageAggregate, InstitutionReport
from analytics.tests.factories import create_organization


def test_analytics_models_are_registered_in_admin():
    assert isinstance(admin.site._registry[DailyUsageAggregate], DailyUsageAggregateAdmin)
    assert isinstance(admin.site._registry[InstitutionReport], InstitutionReportAdmin)
    assert isinstance(admin.site._registry[AnalyticsRun], AnalyticsRunAdmin)


@pytest.mark.django_db
def test_analytics_admins_are_read_only():
    request = RequestFactory().get("/admin/analytics/")
    request.user = type(
        "StaffUser",
        (),
        {"is_active": True, "is_staff": True, "has_perm": lambda self, perm: True},
    )()
    organization = create_organization(slug="admin-report-org")
    report = InstitutionReport.objects.create(
        organization=organization,
        period_start="2026-01-01",
        period_end="2026-01-31",
        metrics={},
    )

    report_admin = admin.site._registry[InstitutionReport]

    assert report_admin.has_add_permission(request) is False
    assert report_admin.has_change_permission(request, report) is False
    assert report_admin.has_delete_permission(request, report) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `python -m pytest analytics/tests/test_admin_registration.py -q`

Expected: FAIL because admin classes are not implemented.

- [ ] **Step 3: Implement admin classes**

Create `backend/analytics/admin.py` with three `ModelAdmin` classes. Each class must:

- define useful `list_display`, `list_filter`, `search_fields`, and `readonly_fields`;
- return `False` from `has_add_permission`;
- return `False` from `has_change_permission`;
- return `False` from `has_delete_permission`.

- [ ] **Step 4: Run analytics tests**

Run from `backend`: `python -m pytest analytics/tests -q`

Expected: PASS.

- [ ] **Step 5: Run full verification**

Run from `backend`:

```bash
python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
```

Run from repo root:

```bash
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit**

```bash
git add backend/analytics backend/config/settings.py backend/pyproject.toml backend/pytest.ini
git commit -m "feat: register analytics admin"
```
