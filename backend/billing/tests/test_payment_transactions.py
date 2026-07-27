import pytest
from django.contrib.auth import get_user_model

from accounts.models import Entitlement, Organization
from billing.models import CommercialOffer, PaymentTransaction
from billing.services import create_payment_transaction


def create_user(email="payment-user@example.ga"):
    return get_user_model().objects.create_user(email=email, password="pass")


def create_offer(slug="payment-offer"):
    return CommercialOffer.objects.create(
        name=f"Payment offer {slug}",
        slug=slug,
        offer_type=CommercialOffer.OfferType.INDIVIDUAL,
        billing_period=CommercialOffer.BillingPeriod.MONTHLY,
        price_xaf=2500,
        duration_days=30,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
    )


@pytest.mark.django_db
def test_create_payment_transaction_is_idempotent_for_same_key_and_terms():
    user = create_user()
    offer = create_offer()

    first = create_payment_transaction(
        idempotency_key="momo-checkout-001",
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
        metadata={"phone": "077000000"},
    )
    second = create_payment_transaction(
        idempotency_key="momo-checkout-001",
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
        metadata={"phone": "077000000"},
    )

    assert second.pk == first.pk
    assert PaymentTransaction.objects.count() == 1
    assert second.metadata == {"phone": "077000000"}


@pytest.mark.django_db
def test_create_payment_transaction_rejects_conflicting_idempotency_reuse():
    user = create_user()
    offer = create_offer()
    create_payment_transaction(
        idempotency_key="momo-conflict",
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
    )

    with pytest.raises(ValueError):
        create_payment_transaction(
            idempotency_key="momo-conflict",
            user=user,
            offer=offer,
            provider=PaymentTransaction.Provider.MOBILE_MONEY,
            amount_xaf=3000,
        )


@pytest.mark.django_db
def test_payment_transaction_mark_pending_and_succeeded_record_provider_reference():
    user = create_user()
    offer = create_offer()
    payment = create_payment_transaction(
        idempotency_key="momo-success",
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
    )

    payment.mark_pending(provider_reference="provider-123")
    payment.mark_succeeded(provider_reference="provider-123")

    payment.refresh_from_db()
    assert payment.status == PaymentTransaction.Status.SUCCEEDED
    assert payment.provider_reference == "provider-123"
    assert payment.pending_at is not None
    assert payment.succeeded_at is not None
    assert payment.failed_at is None


@pytest.mark.django_db
def test_payment_transaction_mark_failed_records_retry_and_reason():
    organization = Organization.objects.create(name="Institution payeuse", slug="institution-payeuse")
    offer = CommercialOffer.objects.create(
        name="Institution annual",
        slug="institution-annual",
        offer_type=CommercialOffer.OfferType.ORGANIZATION,
        billing_period=CommercialOffer.BillingPeriod.ANNUAL,
        price_xaf=500000,
        duration_days=365,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
    )
    payment = create_payment_transaction(
        idempotency_key="invoice-failed",
        organization=organization,
        offer=offer,
        provider=PaymentTransaction.Provider.MANUAL_INVOICE,
        amount_xaf=500000,
    )

    payment.mark_failed(error_code="provider_timeout", message="Provider did not confirm payment")

    payment.refresh_from_db()
    assert payment.status == PaymentTransaction.Status.FAILED
    assert payment.retry_count == 1
    assert payment.failure_code == "provider_timeout"
    assert payment.failure_message == "Provider did not confirm payment"
    assert payment.failed_at is not None
