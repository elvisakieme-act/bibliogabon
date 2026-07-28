# BiblioGABON Operations Admin Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the internal operations foundation for audit logs, publication moderation, support tickets, and Django Admin workflows.

**Architecture:** Create a Django app named `operations` with focused models and service functions. `operations` depends on `accounts`, `catalog`, and `billing`; other apps should consume audit behavior through service functions instead of importing operational models directly.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, pytest, pytest-django, SQLite local/test fallback, PostgreSQL production compatibility.

## Global Constraints

- Operational work must be traceable through durable audit records.
- Moderation and support records must reference existing domain objects instead of duplicating source-of-truth data.
- Django Admin is the first back-office surface for this slice.
- Audit logs are append-only and cannot be added, changed, or deleted through Django Admin.
- Publication decisions and support resolutions must create audit records.
- Do not implement a custom React admin, public support portal, notifications, analytics dashboards, fraud detection, compliance reporting, or object-level staff permission policy in this slice.

---

## File Structure

```text
backend/
  operations/
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
      test_audit_logs.py
      test_bootstrap.py
      test_publication_reviews.py
      test_support_tickets.py
  config/
    settings.py
  pyproject.toml
  pytest.ini
```

---

### Task 1: Operations App Scaffold

**Files:**
- Create: `backend/operations/__init__.py`
- Create: `backend/operations/apps.py`
- Create: `backend/operations/migrations/__init__.py`
- Create: `backend/operations/tests/__init__.py`
- Create: `backend/operations/tests/test_bootstrap.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/pytest.ini`

**Interfaces:**
- Produces installed Django app `operations`.
- Produces `OperationsConfig` with `name = "operations"`.

- [ ] **Step 1: Write the failing bootstrap test**

```python
from django.apps import apps


def test_operations_app_is_installed():
    assert apps.is_installed("operations")
```

- [ ] **Step 2: Run test to verify it fails**

Run from `backend`: `python -m pytest operations/tests/test_bootstrap.py -q`

Expected: FAIL because `operations` is not installed.

- [ ] **Step 3: Add the app scaffold**

Create `backend/operations/apps.py`:

```python
from django.apps import AppConfig


class OperationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "operations"
```

- [ ] **Step 4: Register test paths and app config**

Add `"operations"` to `INSTALLED_APPS` in `backend/config/settings.py`.

Add `operations/tests` to the pytest test path declarations in `backend/pyproject.toml` and `backend/pytest.ini`.

- [ ] **Step 5: Run test to verify it passes**

Run from `backend`: `python -m pytest operations/tests/test_bootstrap.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/operations backend/config/settings.py backend/pyproject.toml backend/pytest.ini
git commit -m "feat: add operations app scaffold"
```

---

### Task 2: Operations Domain Models

**Files:**
- Create: `backend/operations/models.py`
- Create: `backend/operations/tests/factories.py`
- Create: `backend/operations/tests/test_audit_logs.py`
- Create: `backend/operations/tests/test_publication_reviews.py`
- Create: `backend/operations/tests/test_support_tickets.py`
- Generate: `backend/operations/migrations/0001_initial.py`

**Interfaces:**
- Produces `AuditLog`.
- Produces `PublicationReview`.
- Produces `SupportTicket`.
- Produces test helpers `create_user`, `create_organization`, `create_document`, `create_payment_transaction`, and `create_entitlement`.

- [ ] **Step 1: Add shared test factories**

Create `backend/operations/tests/factories.py`:

```python
from django.utils import timezone

from accounts.models import Entitlement, Organization, User
from billing.models import CommercialOffer, PaymentTransaction
from catalog.models import AcademicDomain, Author, Document, DocumentAuthor, RightsAgreement


def create_user(email="staff@example.ga", *, is_staff=False):
    return User.objects.create_user(email=email, password="password", is_staff=is_staff)


def create_organization(slug="operations-org"):
    return Organization.objects.create(
        name=f"Organization {slug}",
        slug=slug,
        organization_type=Organization.OrganizationType.UNIVERSITY,
    )


def create_publishable_document(slug="operations-document"):
    organization = create_organization(slug=f"owner-{slug}")
    domain = AcademicDomain.objects.create(name=f"Domain {slug}", slug=f"domain-{slug}")
    document = Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        owner_organization=organization,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.SUBMITTED,
    )
    author = Author.objects.create(display_name="Author", normalized_name="author")
    DocumentAuthor.objects.create(document=document, author=author, role=DocumentAuthor.Role.AUTHOR)
    RightsAgreement.objects.create(
        document=document,
        rights_holder_name="Rights Holder",
        agreement_type=RightsAgreement.AgreementType.OPEN_LICENSE,
        authorization_status=RightsAgreement.AuthorizationStatus.APPROVED,
        authorization_date=timezone.now().date(),
        access_model=document.access_model,
        withdrawal_rule=RightsAgreement.WithdrawalRule.LICENSE_INVALID,
        reviewer_decision="Approved for publication",
        audit_reference=f"audit-{slug}",
    )
    return document


def create_payment_transaction(user=None):
    user = user or create_user(email="payer@example.ga")
    offer = CommercialOffer.objects.create(
        name="Monthly Access",
        slug="monthly-access",
        offer_type=CommercialOffer.OfferType.INDIVIDUAL,
        billing_period=CommercialOffer.BillingPeriod.MONTHLY,
        price_xaf=1000,
        duration_days=30,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
    )
    return PaymentTransaction.objects.create(
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=1000,
        idempotency_key="operations-payment-key",
    )


def create_entitlement(user=None):
    user = user or create_user(email="entitled@example.ga")
    return Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.ADMIN_GRANT,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
    )
```

- [ ] **Step 2: Write failing model tests**

Add these tests across the three test files:

```python
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from operations.models import AuditLog, PublicationReview, SupportTicket
from operations.tests.factories import create_entitlement, create_payment_transaction, create_publishable_document, create_user


@pytest.mark.django_db
def test_audit_log_requires_event_type_summary_and_dict_metadata():
    actor = create_user(email="audit-actor@example.ga", is_staff=True)
    log = AuditLog(actor=actor, event_type="", summary="", metadata=[])

    with pytest.raises(ValidationError):
        log.full_clean()


@pytest.mark.django_db
def test_publication_review_rejected_requires_decision_reason():
    document = create_publishable_document(slug="rejected-requires-reason")
    review = PublicationReview(
        document=document,
        status=PublicationReview.Status.REJECTED,
        decided_at=timezone.now(),
    )

    with pytest.raises(ValidationError):
        review.full_clean()


@pytest.mark.django_db
def test_support_ticket_resolved_requires_resolution_summary():
    user = create_user(email="support-subject@example.ga")
    ticket = SupportTicket(
        title="Access issue",
        description="Cannot open a document",
        user=user,
        status=SupportTicket.Status.RESOLVED,
        resolved_at=timezone.now(),
    )

    with pytest.raises(ValidationError):
        ticket.full_clean()


@pytest.mark.django_db
def test_support_ticket_can_reference_payment_and_entitlement():
    payment = create_payment_transaction()
    entitlement = create_entitlement(user=payment.user)

    ticket = SupportTicket.objects.create(
        title="Payment access issue",
        description="Payment succeeded but access is missing",
        user=payment.user,
        payment_transaction=payment,
        entitlement=entitlement,
    )

    assert ticket.payment_transaction == payment
    assert ticket.entitlement == entitlement
```

- [ ] **Step 3: Run tests to verify they fail**

Run from `backend`:

```bash
python -m pytest operations/tests/test_audit_logs.py operations/tests/test_publication_reviews.py operations/tests/test_support_tickets.py -q
```

Expected: FAIL because `operations.models` does not define the models.

- [ ] **Step 4: Implement models**

Create `backend/operations/models.py` with:

```python
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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

    class Meta:
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
```

- [ ] **Step 5: Generate migration**

Run from `backend`: `python manage.py makemigrations operations`

Expected: creates `backend/operations/migrations/0001_initial.py`.

- [ ] **Step 6: Run targeted model tests**

Run from `backend`:

```bash
python -m pytest operations/tests/test_audit_logs.py operations/tests/test_publication_reviews.py operations/tests/test_support_tickets.py -q
```

Expected: PASS for model validation and relationship tests.

- [ ] **Step 7: Commit**

```bash
git add backend/operations
git commit -m "feat: add operations domain models"
```

---

### Task 3: Audit Event Service

**Files:**
- Create: `backend/operations/services.py`
- Modify: `backend/operations/tests/test_audit_logs.py`

**Interfaces:**
- Produces `record_audit_event(*, event_type: str, summary: str, actor=None, target=None, metadata: dict | None = None) -> AuditLog`.
- Consumes `AuditLog`.

- [ ] **Step 1: Write failing audit service tests**

Add to `backend/operations/tests/test_audit_logs.py`:

```python
import pytest

from operations.models import AuditLog
from operations.services import record_audit_event
from operations.tests.factories import create_publishable_document, create_user


@pytest.mark.django_db
def test_record_audit_event_stores_actor_target_summary_and_metadata():
    actor = create_user(email="audit-service-actor@example.ga", is_staff=True)
    document = create_publishable_document(slug="audit-target")

    log = record_audit_event(
        actor=actor,
        event_type="publication_review_opened",
        target=document,
        summary="Publication review opened",
        metadata={"document_status": document.publication_status},
    )

    assert log.actor == actor
    assert log.event_type == "publication_review_opened"
    assert log.target_app == "catalog"
    assert log.target_model == "document"
    assert log.target_id == str(document.pk)
    assert log.summary == "Publication review opened"
    assert log.metadata == {"document_status": document.publication_status}


@pytest.mark.django_db
def test_record_audit_event_supports_system_event_without_target():
    log = record_audit_event(
        event_type="system_event",
        summary="Nightly maintenance completed",
        metadata={"job": "maintenance"},
    )

    assert log.actor is None
    assert log.target_app == ""
    assert log.target_model == ""
    assert log.target_id == ""
    assert log.metadata == {"job": "maintenance"}


@pytest.mark.django_db
def test_audit_logs_are_immutable_after_creation():
    log = record_audit_event(event_type="system_event", summary="Created")
    log.summary = "Changed"

    with pytest.raises(ValueError):
        log.save()

    assert AuditLog.objects.get(pk=log.pk).summary == "Created"
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `python -m pytest operations/tests/test_audit_logs.py -q`

Expected: FAIL because `operations.services.record_audit_event` does not exist.

- [ ] **Step 3: Implement audit service**

Create `backend/operations/services.py`:

```python
from __future__ import annotations

from django.db import transaction

from operations.models import AuditLog


def _target_parts(target) -> tuple[str, str, str]:
    if target is None:
        return "", "", ""
    meta = target._meta
    return meta.app_label, meta.model_name, str(target.pk)


def record_audit_event(
    *,
    event_type: str,
    summary: str,
    actor=None,
    target=None,
    metadata: dict | None = None,
) -> AuditLog:
    target_app, target_model, target_id = _target_parts(target)
    with transaction.atomic():
        return AuditLog.objects.create(
            actor=actor,
            event_type=event_type,
            target_app=target_app,
            target_model=target_model,
            target_id=target_id,
            summary=summary,
            metadata=metadata or {},
        )
```

- [ ] **Step 4: Run audit tests**

Run from `backend`: `python -m pytest operations/tests/test_audit_logs.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/operations/services.py backend/operations/tests/test_audit_logs.py
git commit -m "feat: record operations audit events"
```

---

### Task 4: Publication Review Services

**Files:**
- Modify: `backend/operations/services.py`
- Modify: `backend/operations/tests/test_publication_reviews.py`

**Interfaces:**
- Consumes `record_audit_event(...) -> AuditLog`.
- Produces `open_publication_review(*, document, actor=None, reviewer=None, internal_notes="") -> PublicationReview`.
- Produces `record_publication_decision(*, review, decision: str, actor=None, reason: str = "", at=None) -> PublicationReview`.

- [ ] **Step 1: Write failing publication workflow tests**

Add to `backend/operations/tests/test_publication_reviews.py`:

```python
import pytest

from catalog.models import Document
from operations.models import AuditLog, PublicationReview
from operations.services import open_publication_review, record_publication_decision
from operations.tests.factories import create_publishable_document, create_user


@pytest.mark.django_db
def test_open_publication_review_creates_open_review_and_audit_event():
    actor = create_user(email="review-opener@example.ga", is_staff=True)
    reviewer = create_user(email="reviewer@example.ga", is_staff=True)
    document = create_publishable_document(slug="open-review")

    review = open_publication_review(
        document=document,
        actor=actor,
        reviewer=reviewer,
        internal_notes="Check rights before publication",
    )

    assert review.document == document
    assert review.status == PublicationReview.Status.OPEN
    assert review.opened_by == actor
    assert review.reviewer == reviewer
    assert review.internal_notes == "Check rights before publication"
    assert AuditLog.objects.filter(
        event_type="publication_review_opened",
        target_app="catalog",
        target_model="document",
        target_id=str(document.pk),
    ).exists()


@pytest.mark.django_db
def test_approving_publication_review_publishes_document_and_records_audit():
    actor = create_user(email="review-approver@example.ga", is_staff=True)
    document = create_publishable_document(slug="approve-review")
    review = open_publication_review(document=document, actor=actor)

    decided = record_publication_decision(
        review=review,
        decision=PublicationReview.Status.APPROVED,
        actor=actor,
        reason="Rights and metadata approved",
    )

    document.refresh_from_db()
    assert decided.status == PublicationReview.Status.APPROVED
    assert decided.decided_by == actor
    assert decided.decision_reason == "Rights and metadata approved"
    assert decided.decided_at is not None
    assert document.publication_status == Document.PublicationStatus.PUBLISHED
    assert document.published_at is not None
    assert AuditLog.objects.filter(event_type="publication_review_approved", target_id=str(document.pk)).exists()


@pytest.mark.django_db
def test_rejecting_publication_review_rejects_document_and_records_audit():
    actor = create_user(email="review-rejecter@example.ga", is_staff=True)
    document = create_publishable_document(slug="reject-review")
    review = open_publication_review(document=document, actor=actor)

    decided = record_publication_decision(
        review=review,
        decision=PublicationReview.Status.REJECTED,
        actor=actor,
        reason="Missing required institutional approval",
    )

    document.refresh_from_db()
    assert decided.status == PublicationReview.Status.REJECTED
    assert document.publication_status == Document.PublicationStatus.REJECTED
    assert document.published_at is None
    assert AuditLog.objects.filter(event_type="publication_review_rejected", target_id=str(document.pk)).exists()


@pytest.mark.django_db
def test_approval_rejects_document_that_is_not_publishable():
    actor = create_user(email="not-publishable-reviewer@example.ga", is_staff=True)
    document = create_publishable_document(slug="not-publishable-review")
    document.academic_domain = None
    document.save(update_fields=["academic_domain", "updated_at"])
    review = open_publication_review(document=document, actor=actor)

    with pytest.raises(ValueError):
        record_publication_decision(
            review=review,
            decision=PublicationReview.Status.APPROVED,
            actor=actor,
            reason="Attempted approval",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `python -m pytest operations/tests/test_publication_reviews.py -q`

Expected: FAIL because publication review services do not exist.

- [ ] **Step 3: Implement publication services**

Add to `backend/operations/services.py`:

```python
from django.db import transaction
from django.utils import timezone

from catalog.models import Document
from catalog.services import document_is_publishable
from operations.models import PublicationReview


def open_publication_review(*, document, actor=None, reviewer=None, internal_notes="") -> PublicationReview:
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document.pk)
        existing = PublicationReview.objects.filter(
            document=document,
            status=PublicationReview.Status.OPEN,
        ).first()
        if existing:
            return existing
        review = PublicationReview.objects.create(
            document=document,
            opened_by=actor,
            reviewer=reviewer,
            internal_notes=internal_notes,
        )
        record_audit_event(
            actor=actor,
            event_type="publication_review_opened",
            target=document,
            summary=f"Publication review opened for {document.title}",
            metadata={"review_id": review.pk, "reviewer_id": reviewer.pk if reviewer else None},
        )
        return review


def record_publication_decision(*, review, decision: str, actor=None, reason: str = "", at=None) -> PublicationReview:
    at = at or timezone.now()
    if decision not in {
        PublicationReview.Status.APPROVED,
        PublicationReview.Status.REJECTED,
        PublicationReview.Status.CANCELLED,
    }:
        raise ValueError("decision must close the publication review")
    if decision == PublicationReview.Status.REJECTED and not reason.strip():
        raise ValueError("rejected reviews require decision reason")

    with transaction.atomic():
        review = (
            PublicationReview.objects.select_for_update()
            .select_related("document")
            .get(pk=review.pk)
        )
        if review.status != PublicationReview.Status.OPEN:
            raise ValueError("publication review is already closed")
        document = Document.objects.select_for_update().get(pk=review.document_id)
        if decision == PublicationReview.Status.APPROVED and not document_is_publishable(document):
            raise ValueError("document is not publishable")

        review.status = decision
        review.decided_by = actor
        review.decision_reason = reason
        review.decided_at = at
        review.save(update_fields=["status", "decided_by", "decision_reason", "decided_at", "updated_at"])

        if decision == PublicationReview.Status.APPROVED:
            document.publication_status = Document.PublicationStatus.PUBLISHED
            document.published_at = at
            document.withdrawn_at = None
            document.save(update_fields=["publication_status", "published_at", "withdrawn_at", "updated_at"])
            event_type = "publication_review_approved"
        elif decision == PublicationReview.Status.REJECTED:
            document.publication_status = Document.PublicationStatus.REJECTED
            document.published_at = None
            document.save(update_fields=["publication_status", "published_at", "updated_at"])
            event_type = "publication_review_rejected"
        else:
            event_type = "publication_review_cancelled"

        record_audit_event(
            actor=actor,
            event_type=event_type,
            target=document,
            summary=f"Publication review {decision} for {document.title}",
            metadata={"review_id": review.pk, "decision_reason": reason},
        )
        return review
```

- [ ] **Step 4: Run publication tests**

Run from `backend`: `python -m pytest operations/tests/test_publication_reviews.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/operations/services.py backend/operations/tests/test_publication_reviews.py
git commit -m "feat: manage publication reviews"
```

---

### Task 5: Support Ticket Services

**Files:**
- Modify: `backend/operations/services.py`
- Modify: `backend/operations/tests/test_support_tickets.py`

**Interfaces:**
- Consumes `record_audit_event(...) -> AuditLog`.
- Produces `open_support_ticket(*, title: str, description: str, created_by=None, assigned_to=None, priority: str = SupportTicket.Priority.NORMAL, user=None, organization=None, document=None, payment_transaction=None, entitlement=None) -> SupportTicket`.
- Produces `resolve_support_ticket(*, ticket, actor=None, resolution_summary: str, at=None) -> SupportTicket`.

- [ ] **Step 1: Write failing support workflow tests**

Add to `backend/operations/tests/test_support_tickets.py`:

```python
import pytest

from operations.models import AuditLog, SupportTicket
from operations.services import open_support_ticket, resolve_support_ticket
from operations.tests.factories import create_payment_transaction, create_user


@pytest.mark.django_db
def test_open_support_ticket_records_context_and_audit_event():
    staff = create_user(email="support-agent@example.ga", is_staff=True)
    payment = create_payment_transaction()

    ticket = open_support_ticket(
        title="Payment access issue",
        description="User paid but cannot read",
        created_by=staff,
        user=payment.user,
        payment_transaction=payment,
        priority=SupportTicket.Priority.HIGH,
    )

    assert ticket.status == SupportTicket.Status.OPEN
    assert ticket.created_by == staff
    assert ticket.user == payment.user
    assert ticket.payment_transaction == payment
    assert ticket.priority == SupportTicket.Priority.HIGH
    assert AuditLog.objects.filter(
        event_type="support_ticket_opened",
        target_app="operations",
        target_model="supportticket",
        target_id=str(ticket.pk),
    ).exists()


@pytest.mark.django_db
def test_resolve_support_ticket_closes_ticket_and_records_audit_event():
    staff = create_user(email="support-resolver@example.ga", is_staff=True)
    ticket = open_support_ticket(
        title="Reader access issue",
        description="Session cannot load",
        created_by=staff,
    )

    resolved = resolve_support_ticket(
        ticket=ticket,
        actor=staff,
        resolution_summary="Reader session was reset",
    )

    assert resolved.status == SupportTicket.Status.RESOLVED
    assert resolved.resolution_summary == "Reader session was reset"
    assert resolved.resolved_at is not None
    assert AuditLog.objects.filter(event_type="support_ticket_resolved", target_id=str(ticket.pk)).exists()


@pytest.mark.django_db
def test_resolve_support_ticket_requires_resolution_summary():
    ticket = open_support_ticket(title="Missing access", description="Access missing")

    with pytest.raises(ValueError):
        resolve_support_ticket(ticket=ticket, resolution_summary="")


@pytest.mark.django_db
def test_resolve_support_ticket_rejects_already_closed_ticket():
    ticket = open_support_ticket(title="Duplicate closure", description="Close once")
    resolve_support_ticket(ticket=ticket, resolution_summary="Closed")

    with pytest.raises(ValueError):
        resolve_support_ticket(ticket=ticket, resolution_summary="Closed again")
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `python -m pytest operations/tests/test_support_tickets.py -q`

Expected: FAIL because support ticket services do not exist.

- [ ] **Step 3: Implement support services**

Add to `backend/operations/services.py`:

```python
from operations.models import SupportTicket


def open_support_ticket(
    *,
    title: str,
    description: str,
    created_by=None,
    assigned_to=None,
    priority: str = SupportTicket.Priority.NORMAL,
    user=None,
    organization=None,
    document=None,
    payment_transaction=None,
    entitlement=None,
) -> SupportTicket:
    with transaction.atomic():
        ticket = SupportTicket.objects.create(
            title=title,
            description=description,
            created_by=created_by,
            assigned_to=assigned_to,
            priority=priority,
            user=user,
            organization=organization,
            document=document,
            payment_transaction=payment_transaction,
            entitlement=entitlement,
        )
        record_audit_event(
            actor=created_by,
            event_type="support_ticket_opened",
            target=ticket,
            summary=f"Support ticket opened: {ticket.title}",
            metadata={
                "priority": ticket.priority,
                "user_id": user.pk if user else None,
                "organization_id": organization.pk if organization else None,
                "document_id": document.pk if document else None,
                "payment_transaction_id": payment_transaction.pk if payment_transaction else None,
                "entitlement_id": entitlement.pk if entitlement else None,
            },
        )
        return ticket


def resolve_support_ticket(*, ticket, actor=None, resolution_summary: str, at=None) -> SupportTicket:
    if not resolution_summary.strip():
        raise ValueError("resolution_summary is required")
    at = at or timezone.now()
    with transaction.atomic():
        ticket = SupportTicket.objects.select_for_update().get(pk=ticket.pk)
        if ticket.status in {SupportTicket.Status.RESOLVED, SupportTicket.Status.CANCELLED}:
            raise ValueError("support ticket is already closed")
        ticket.status = SupportTicket.Status.RESOLVED
        ticket.resolution_summary = resolution_summary
        ticket.resolved_at = at
        ticket.save(update_fields=["status", "resolution_summary", "resolved_at", "updated_at"])
        record_audit_event(
            actor=actor,
            event_type="support_ticket_resolved",
            target=ticket,
            summary=f"Support ticket resolved: {ticket.title}",
            metadata={"resolution_summary": resolution_summary},
        )
        return ticket
```

- [ ] **Step 4: Run support tests**

Run from `backend`: `python -m pytest operations/tests/test_support_tickets.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/operations/services.py backend/operations/tests/test_support_tickets.py
git commit -m "feat: manage support tickets"
```

---

### Task 6: Django Admin Registration And Safety

**Files:**
- Create: `backend/operations/admin.py`
- Create: `backend/operations/tests/test_admin_registration.py`

**Interfaces:**
- Registers `AuditLog`, `PublicationReview`, and `SupportTicket` in Django Admin.
- Produces `AuditLogAdmin.has_add_permission() -> False`.
- Produces `AuditLogAdmin.has_change_permission() -> False`.
- Produces `AuditLogAdmin.has_delete_permission() -> False`.

- [ ] **Step 1: Write failing admin tests**

Create `backend/operations/tests/test_admin_registration.py`:

```python
from django.contrib import admin

from operations.admin import AuditLogAdmin, PublicationReviewAdmin, SupportTicketAdmin
from operations.models import AuditLog, PublicationReview, SupportTicket


def test_operations_models_are_registered_in_admin():
    assert isinstance(admin.site._registry[AuditLog], AuditLogAdmin)
    assert isinstance(admin.site._registry[PublicationReview], PublicationReviewAdmin)
    assert isinstance(admin.site._registry[SupportTicket], SupportTicketAdmin)


def test_audit_log_admin_is_read_only(rf):
    model_admin = admin.site._registry[AuditLog]
    request = rf.get("/admin/operations/auditlog/")

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False


def test_operations_admin_search_filter_and_readonly_configuration():
    audit_admin = admin.site._registry[AuditLog]
    review_admin = admin.site._registry[PublicationReview]
    ticket_admin = admin.site._registry[SupportTicket]

    assert "event_type" in audit_admin.list_filter
    assert "summary" in audit_admin.search_fields
    assert "created_at" in audit_admin.readonly_fields
    assert "status" in review_admin.list_filter
    assert "document__title" in review_admin.search_fields
    assert "status" in ticket_admin.list_filter
    assert "user__email" in ticket_admin.search_fields
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `python -m pytest operations/tests/test_admin_registration.py -q`

Expected: FAIL because the admin classes are missing.

- [ ] **Step 3: Implement admin classes**

Create `backend/operations/admin.py`:

```python
from django.contrib import admin

from operations.models import AuditLog, PublicationReview, SupportTicket


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "event_type", "actor", "target", "summary"]
    list_filter = ["event_type", "target_app", "target_model", "created_at"]
    search_fields = ["actor__email", "summary", "target_app", "target_model", "target_id"]
    readonly_fields = ["actor", "event_type", "target_app", "target_model", "target_id", "summary", "metadata", "created_at"]

    @admin.display(description="Target")
    def target(self, obj: AuditLog) -> str:
        if not obj.target_model:
            return "system"
        return f"{obj.target_app}.{obj.target_model}:{obj.target_id}"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PublicationReview)
class PublicationReviewAdmin(admin.ModelAdmin):
    list_display = ["document", "status", "reviewer", "opened_by", "decided_by", "opened_at", "decided_at"]
    list_filter = ["status", "opened_at", "decided_at"]
    search_fields = ["document__title", "reviewer__email", "opened_by__email", "decided_by__email", "decision_reason", "internal_notes"]
    autocomplete_fields = ["document", "opened_by", "reviewer", "decided_by"]
    readonly_fields = ["opened_at", "decided_at", "created_at", "updated_at"]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "priority", "assigned_to", "user", "organization", "opened_at", "resolved_at"]
    list_filter = ["status", "priority", "opened_at", "resolved_at"]
    search_fields = [
        "title",
        "description",
        "resolution_summary",
        "user__email",
        "organization__name",
        "document__title",
        "payment_transaction__idempotency_key",
        "payment_transaction__provider_reference",
    ]
    autocomplete_fields = [
        "created_by",
        "assigned_to",
        "user",
        "organization",
        "document",
        "payment_transaction",
        "entitlement",
    ]
    readonly_fields = ["opened_at", "resolved_at", "created_at", "updated_at"]
```

- [ ] **Step 4: Run admin tests**

Run from `backend`: `python -m pytest operations/tests/test_admin_registration.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/operations/admin.py backend/operations/tests/test_admin_registration.py
git commit -m "test: cover operations admin"
```

---

### Task 7: Full Verification And Review

**Files:**
- Modify only files flagged by verification or review findings.

**Interfaces:**
- Produces an operations slice ready for merge choice.

- [ ] **Step 1: Run full backend verification**

Run from `backend`:

```bash
python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
```

Run from repository root:

```bash
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 2: Request review**

Request review focused on:

```text
- Audit log immutability and admin safety.
- Publication decision consistency with catalog publishability rules.
- Support ticket state transitions and audit coverage.
- Migration compatibility with SQLite tests and PostgreSQL production.
- Test coverage for success, denial, and boundary conditions.
```

- [ ] **Step 3: Verify each review finding**

For each finding:

```text
1. Reproduce or inspect the exact code path.
2. Decide whether the finding is valid for this codebase.
3. If valid, write a failing regression test first.
4. Implement the smallest production change that makes the test pass.
5. Run the targeted test.
```

- [ ] **Step 4: Rerun full verification**

Run the same commands from Step 1.

Expected: all commands exit 0.

- [ ] **Step 5: Commit review fixes**

If review produced changes:

```bash
git add backend/operations
git commit -m "fix: harden operations workflows"
```

If review produced no changes, do not create an empty commit.

- [ ] **Step 6: Present finishing options**

Use `superpowers:finishing-a-development-branch` and present the standard merge, PR, or keep-as-is options.
