import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from operations.models import SupportTicket
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
