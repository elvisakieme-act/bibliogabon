from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from catalog.models import Document
from catalog.services import document_is_publishable
from operations.models import AuditLog, PublicationReview, SupportTicket


def _target_parts(target) -> tuple[str, str, str]:
    if target is None:
        return "", "", ""
    if target._state.adding or target.pk is None:
        raise ValueError("target must be saved")
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
            metadata=metadata if metadata is not None else {},
        )


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
