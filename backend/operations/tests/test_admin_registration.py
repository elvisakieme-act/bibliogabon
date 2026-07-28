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
