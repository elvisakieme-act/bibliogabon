from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from catalog.models import Document
from catalog.services import document_is_publishable
from operations.models import AuditLog, PublicationReview, SupportTicket


def _truncate_audit_summary(summary: str) -> str:
    max_length = AuditLog._meta.get_field("summary").max_length
    return summary[:max_length]


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


def open_publication_review(
    *, document, actor=None, reviewer=None, internal_notes=""
) -> PublicationReview:
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
            summary=_truncate_audit_summary(f"Publication review opened for {document.title}"),
            metadata={"review_id": review.pk, "reviewer_id": reviewer.pk if reviewer else None},
        )
        return review


def _apply_publication_decision(document, decision: str, at) -> str:
    """Porte la decision sur le document et nomme l'evenement d'audit.
    Une annulation ne touche pas au document : elle ferme la revue en
    laissant la publication dans l'etat ou elle l'a trouvee."""
    if decision == PublicationReview.Status.APPROVED:
        document.publication_status = Document.PublicationStatus.PUBLISHED
        document.published_at = at
        # Republier apres un retrait doit effacer la date de retrait, sinon
        # le document reste marque comme retire tout en etant lisible.
        document.withdrawn_at = None
        document.save(
            update_fields=["publication_status", "published_at", "withdrawn_at", "updated_at"]
        )
        return "publication_review_approved"
    if decision == PublicationReview.Status.REJECTED:
        document.publication_status = Document.PublicationStatus.REJECTED
        document.published_at = None
        document.save(update_fields=["publication_status", "published_at", "updated_at"])
        return "publication_review_rejected"
    return "publication_review_cancelled"


def record_publication_decision(
    *, review, decision: str, actor=None, reason: str = "", at=None
) -> PublicationReview:
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
        if decision == PublicationReview.Status.APPROVED and not document_is_publishable(
            document
        ):
            raise ValueError("document is not publishable")

        review.status = decision
        review.decided_by = actor
        review.decision_reason = reason
        review.decided_at = at
        review.save(
            update_fields=[
                "status",
                "decided_by",
                "decision_reason",
                "decided_at",
                "updated_at",
            ]
        )

        event_type = _apply_publication_decision(document, decision, at)
        record_audit_event(
            actor=actor,
            event_type=event_type,
            target=document,
            summary=_truncate_audit_summary(
                f"Publication review {decision} for {document.title}"
            ),
            metadata={"review_id": review.pk, "decision_reason": reason},
        )
        return review


def _close_publication(
    *,
    document,
    target_status: str,
    event_type: str,
    verb: str,
    reason: str,
    actor,
    at,
    allowed_from: set[str],
):
    """Sort un document du public, en enregistrant qui et pourquoi.

    Retrait et archivage ne diffèrent que par l'état visé, ce qui est attendu,
    et par les états d'où ils partent, ce qui l'est moins : on ne retire pas ce
    qui n'a jamais paru, et on n'archive pas deux fois.

    Ni l'un ni l'autre ne supprime quoi que ce soit. La gouvernance exige que
    le retrait soit réversible en interne : les pages, la version, l'index et
    les droits restent, et seule la lisibilité change — `document_is_reader_
    accessible` teste `published`. Les droits en particulier ne sont pas
    touchés : confondre retrait et révocation ferait exiger une nouvelle
    approbation à une republication qui n'en a pas besoin.
    """
    reason = (reason or "").strip()
    if not reason:
        # Un document public qui disparaît sans motif enregistré est exactement
        # ce qu'un audit sert à empêcher.
        raise ValueError(f"{verb} requires a reason")
    if actor is None:
        # Un acte anonyme est intraçable, ce qui vide l'audit de son sens.
        raise ValueError(f"{verb} requires an actor")

    at = at or timezone.now()
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document.pk)
        if document.publication_status not in allowed_from:
            raise ValueError(f"cannot {verb} a document in state {document.publication_status}")

        document.publication_status = target_status
        update_fields = ["publication_status", "updated_at"]
        if target_status == Document.PublicationStatus.WITHDRAWN:
            document.withdrawn_at = at
            update_fields.append("withdrawn_at")
        document.save(update_fields=update_fields)

        record_audit_event(
            actor=actor,
            event_type=event_type,
            target=document,
            summary=_truncate_audit_summary(f"{verb.capitalize()}: {document.title}"),
            # Le motif complet vit dans `metadata` : le résumé est borné à 240
            # caractères et le tronquerait.
            metadata={"document_id": document.pk, "reason": reason},
        )
        return document


def withdraw_document(*, document, reason: str, actor=None, at=None) -> Document:
    """Retire un document du public. Réversible par une nouvelle décision."""
    return _close_publication(
        document=document,
        target_status=Document.PublicationStatus.WITHDRAWN,
        event_type="document_withdrawn",
        verb="withdraw",
        reason=reason,
        actor=actor,
        at=at,
        allowed_from={Document.PublicationStatus.PUBLISHED},
    )


def archive_document(*, document, reason: str, actor=None, at=None) -> Document:
    """Archive un document : fin de sa vie sur la plateforme.

    Distinct du retrait, qui est réversible. Un document archivé se ferme, et
    l'archivage part donc aussi bien d'un document publié que retiré.
    """
    return _close_publication(
        document=document,
        target_status=Document.PublicationStatus.ARCHIVED,
        event_type="document_archived",
        verb="archive",
        reason=reason,
        actor=actor,
        at=at,
        allowed_from={
            Document.PublicationStatus.PUBLISHED,
            Document.PublicationStatus.WITHDRAWN,
        },
    )


def open_support_ticket(
    *,
    title: str,
    description: str,
    created_by=None,
    assigned_to=None,
    category: str = SupportTicket.Category.SUPPORT,
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
            category=category,
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
                "category": ticket.category,
                "priority": ticket.priority,
                "user_id": user.pk if user else None,
                "organization_id": organization.pk if organization else None,
                "document_id": document.pk if document else None,
                "payment_transaction_id": payment_transaction.pk
                if payment_transaction
                else None,
                "entitlement_id": entitlement.pk if entitlement else None,
            },
        )
        return ticket


def _open_document_ticket(
    *,
    document,
    reason: str,
    actor,
    category: str,
    priority: str,
    title: str,
    event_type: str,
    verb: str,
) -> SupportTicket:
    reason = (reason or "").strip()
    if not reason:
        raise ValueError(f"{verb} requires a reason")
    if actor is None:
        # Un signalement anonyme n'est pas traçable, et le traiter demanderait
        # de recontacter quelqu'un dont on ne sait rien.
        raise ValueError(f"{verb} requires an actor")

    ticket = open_support_ticket(
        title=_truncate_audit_summary(f"{title} : {document.title}"),
        description=reason,
        created_by=actor,
        category=category,
        priority=priority,
        user=actor,
        document=document,
        organization=document.owner_organization,
    )
    record_audit_event(
        actor=actor,
        event_type=event_type,
        target=document,
        summary=_truncate_audit_summary(f"{title} : {document.title}"),
        metadata={"document_id": document.pk, "reason": reason, "ticket_id": ticket.pk},
    )
    return ticket


def report_document(*, document, reason: str, reported_by=None, at=None) -> SupportTicket:
    """Signalement d'un document par un lecteur."""
    return _open_document_ticket(
        document=document,
        reason=reason,
        actor=reported_by,
        category=SupportTicket.Category.DOCUMENT_REPORT,
        priority=SupportTicket.Priority.NORMAL,
        title="Signalement",
        event_type="document_reported",
        verb="report",
    )


def request_document_withdrawal(
    *, document, reason: str, requested_by=None, at=None
) -> SupportTicket:
    """Demande de retrait — qui ne retire rien.

    Un auteur qui retirerait directement contournerait les règles
    contractuelles encodées dans `can_withdraw_document` : un fonds
    institutionnel ne se retire pas unilatéralement. La demande crée donc un
    ticket qu'un modérateur traite avec `withdraw_document`, lequel exige un
    motif et écrit un événement d'audit.

    Priorité haute : une demande peut porter sur des droits ou une
    confidentialité, et n'a pas à attendre derrière une question de facturation.
    """
    if document.publication_status != Document.PublicationStatus.PUBLISHED:
        # Il n'y a rien à retirer d'un brouillon : accepter la demande
        # promettrait un acte qui ne peut pas avoir lieu.
        raise ValueError("only a published document can be requested for withdrawal")

    return _open_document_ticket(
        document=document,
        reason=reason,
        actor=requested_by,
        category=SupportTicket.Category.WITHDRAWAL_REQUEST,
        priority=SupportTicket.Priority.HIGH,
        title="Demande de retrait",
        event_type="document_withdrawal_requested",
        verb="withdrawal request",
    )


def resolve_support_ticket(
    *, ticket, actor=None, resolution_summary: str, at=None
) -> SupportTicket:
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
