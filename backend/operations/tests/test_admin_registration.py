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
