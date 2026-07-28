from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from catalog.models import Document
from catalog.services import document_is_publishable
from operations.models import AuditLog, PublicationReview


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
