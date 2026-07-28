from django.contrib import admin

from operations.models import AuditLog, PublicationReview, SupportTicket
from operations.services import record_publication_decision, resolve_support_ticket


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
    readonly_fields = ["status", "decided_by", "opened_at", "decided_at", "created_at", "updated_at"]

    @admin.action(description="Approve selected publication reviews")
    def approve_reviews(self, request, queryset):
        for review in queryset.filter(status=PublicationReview.Status.OPEN):
            record_publication_decision(
                review=review,
                decision=PublicationReview.Status.APPROVED,
                actor=request.user,
                reason=review.decision_reason,
            )


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
    readonly_fields = ["status", "resolved_at", "created_at", "updated_at"]

    @admin.action(description="Resolve selected support tickets")
    def resolve_tickets(self, request, queryset):
        for ticket in queryset.filter(status__in=[
            SupportTicket.Status.OPEN,
            SupportTicket.Status.IN_PROGRESS,
            SupportTicket.Status.WAITING,
        ]):
            resolve_support_ticket(
                ticket=ticket,
                actor=request.user,
                resolution_summary=ticket.resolution_summary,
            )
