from django.contrib import admin
from django.test import RequestFactory
import pytest

from operations.admin import AuditLogAdmin, PublicationReviewAdmin, SupportTicketAdmin
from catalog.models import Document
from operations.models import AuditLog, PublicationReview, SupportTicket
from operations.services import open_publication_review, open_support_ticket
from operations.tests.factories import create_publishable_document, create_user


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


@pytest.mark.django_db
def test_publication_review_admin_requires_audited_approval_action():
    actor = create_user(email="admin-approver@example.ga", is_staff=True)
    document = create_publishable_document(slug="admin-approve-review")
    review = open_publication_review(document=document, actor=actor)
    review.decision_reason = "Rights and metadata approved"
    review.save(update_fields=["decision_reason", "updated_at"])
    model_admin = admin.site._registry[PublicationReview]
    request = RequestFactory().post("/admin/operations/publicationreview/")
    request.user = actor

    form = model_admin.get_form(request)(instance=review)
    assert "status" not in form.base_fields
    assert "decided_by" not in form.base_fields
    assert "decided_at" not in form.base_fields

    model_admin.approve_reviews(request, PublicationReview.objects.filter(pk=review.pk))

    review.refresh_from_db()
    document.refresh_from_db()
    assert review.status == PublicationReview.Status.APPROVED
    assert document.publication_status == Document.PublicationStatus.PUBLISHED
    assert AuditLog.objects.filter(
        event_type="publication_review_approved",
        target_id=str(document.pk),
        actor=actor,
    ).exists()


@pytest.mark.django_db
def test_support_ticket_admin_requires_audited_resolution_action():
    actor = create_user(email="admin-resolver@example.ga", is_staff=True)
    ticket = open_support_ticket(
        title="Admin resolution",
        description="Needs an audited resolution",
        created_by=actor,
    )
    ticket.resolution_summary = "Reader session was reset"
    ticket.save(update_fields=["resolution_summary", "updated_at"])
    model_admin = admin.site._registry[SupportTicket]
    request = RequestFactory().post("/admin/operations/supportticket/")
    request.user = actor

    form = model_admin.get_form(request)(instance=ticket)
    assert "status" not in form.base_fields
    assert "resolved_at" not in form.base_fields

    model_admin.resolve_tickets(request, SupportTicket.objects.filter(pk=ticket.pk))

    ticket.refresh_from_db()
    assert ticket.status == SupportTicket.Status.RESOLVED
    assert ticket.resolved_at is not None
    assert AuditLog.objects.filter(
        event_type="support_ticket_resolved",
        target_id=str(ticket.pk),
        actor=actor,
    ).exists()


@pytest.mark.django_db
def test_publication_review_admin_reject_action_is_audited():
    actor = create_user(email="admin-rejecter@example.ga", is_staff=True)
    document = create_publishable_document(slug="admin-reject-review")
    review = open_publication_review(document=document, actor=actor)
    review.decision_reason = "Missing institutional approval"
    review.save(update_fields=["decision_reason", "updated_at"])
    model_admin = admin.site._registry[PublicationReview]
    request = RequestFactory().post("/admin/operations/publicationreview/")
    request.user = actor

    model_admin.reject_reviews(request, PublicationReview.objects.filter(pk=review.pk))

    review.refresh_from_db()
    document.refresh_from_db()
    assert review.status == PublicationReview.Status.REJECTED
    assert document.publication_status == Document.PublicationStatus.REJECTED
    assert AuditLog.objects.filter(
        event_type="publication_review_rejected",
        target_id=str(document.pk),
        actor=actor,
    ).exists()


@pytest.mark.django_db
def test_publication_review_admin_cancel_action_is_audited():
    actor = create_user(email="admin-canceller@example.ga", is_staff=True)
    document = create_publishable_document(slug="admin-cancel-review")
    review = open_publication_review(document=document, actor=actor)
    model_admin = admin.site._registry[PublicationReview]
    request = RequestFactory().post("/admin/operations/publicationreview/")
    request.user = actor

    model_admin.cancel_reviews(request, PublicationReview.objects.filter(pk=review.pk))

    review.refresh_from_db()
    assert review.status == PublicationReview.Status.CANCELLED
    assert AuditLog.objects.filter(
        event_type="publication_review_cancelled",
        target_id=str(document.pk),
        actor=actor,
    ).exists()


@pytest.mark.django_db
def test_publication_review_admin_reports_error_and_rolls_back_batch(monkeypatch):
    actor = create_user(email="admin-batch-approver@example.ga", is_staff=True)
    valid_document = create_publishable_document(slug="admin-valid-batch-review")
    invalid_document = create_publishable_document(slug="admin-invalid-batch-review")
    invalid_document.academic_domain = None
    invalid_document.save(update_fields=["academic_domain", "updated_at"])
    valid_review = open_publication_review(document=valid_document, actor=actor)
    invalid_review = open_publication_review(document=invalid_document, actor=actor)
    queryset = PublicationReview.objects.filter(pk__in=[valid_review.pk, invalid_review.pk])
    model_admin = admin.site._registry[PublicationReview]
    request = RequestFactory().post("/admin/operations/publicationreview/")
    request.user = actor
    errors = []
    monkeypatch.setattr(model_admin, "message_user", lambda request, message, **kwargs: errors.append(message))

    model_admin.approve_reviews(request, queryset)

    valid_review.refresh_from_db()
    invalid_review.refresh_from_db()
    assert valid_review.status == PublicationReview.Status.OPEN
    assert invalid_review.status == PublicationReview.Status.OPEN
    assert not AuditLog.objects.filter(event_type="publication_review_approved").exists()
    assert any("not publishable" in message for message in errors)


@pytest.mark.django_db
def test_support_ticket_admin_reports_error_and_rolls_back_batch(monkeypatch):
    actor = create_user(email="admin-batch-resolver@example.ga", is_staff=True)
    valid_ticket = open_support_ticket(
        title="Valid batch ticket",
        description="Has a resolution",
        created_by=actor,
    )
    valid_ticket.resolution_summary = "Reader session was reset"
    valid_ticket.save(update_fields=["resolution_summary", "updated_at"])
    invalid_ticket = open_support_ticket(
        title="Invalid batch ticket",
        description="Has no resolution",
        created_by=actor,
    )
    queryset = SupportTicket.objects.filter(pk__in=[valid_ticket.pk, invalid_ticket.pk])
    model_admin = admin.site._registry[SupportTicket]
    request = RequestFactory().post("/admin/operations/supportticket/")
    request.user = actor
    errors = []
    monkeypatch.setattr(model_admin, "message_user", lambda request, message, **kwargs: errors.append(message))

    model_admin.resolve_tickets(request, queryset)

    valid_ticket.refresh_from_db()
    invalid_ticket.refresh_from_db()
    assert valid_ticket.status == SupportTicket.Status.OPEN
    assert invalid_ticket.status == SupportTicket.Status.OPEN
    assert not AuditLog.objects.filter(event_type="support_ticket_resolved").exists()
    assert any("resolution_summary is required" in message for message in errors)
