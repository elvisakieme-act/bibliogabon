import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from operations.models import AuditLog, SupportTicket
from operations.services import open_support_ticket, resolve_support_ticket
from operations.tests.factories import create_entitlement, create_payment_transaction, create_user


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
