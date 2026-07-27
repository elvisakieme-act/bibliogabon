import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet

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
def test_create_payment_transaction_reuses_existing_row_after_unique_validation_race(monkeypatch):
    user = create_user(email="race-user@example.ga")
    offer = create_offer(slug="race-offer")
    existing = create_payment_transaction(
        idempotency_key="race-key",
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
    )
    original_get_or_create = QuerySet.get_or_create
    calls = {"count": 0}

    def raise_unique_validation_once(queryset, *args, **kwargs):
        if queryset.model is PaymentTransaction and kwargs.get("idempotency_key") == "race-key":
            calls["count"] += 1
            if calls["count"] == 1:
                raise ValidationError({"idempotency_key": ["Payment transaction with this key already exists."]})
        return original_get_or_create(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "get_or_create", raise_unique_validation_once)

    repeated = create_payment_transaction(
        idempotency_key="race-key",
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
    )

    assert repeated.pk == existing.pk


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
def test_succeeded_payment_transaction_cannot_regress_to_failed_or_pending():
    user = create_user(email="terminal-payment@example.ga")
    offer = create_offer(slug="terminal-payment")
    payment = create_payment_transaction(
        idempotency_key="terminal-success",
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
    )
    payment.mark_succeeded(provider_reference="provider-terminal")

    with pytest.raises(ValueError):
        payment.mark_failed(error_code="late_failure", message="Late failure callback")
    with pytest.raises(ValueError):
        payment.mark_pending(provider_reference="late-pending")

    payment.refresh_from_db()
    assert payment.status == PaymentTransaction.Status.SUCCEEDED
    assert payment.provider_reference == "provider-terminal"


@pytest.mark.django_db
def test_stale_payment_instance_cannot_overwrite_succeeded_payment():
    user = create_user(email="stale-payment@example.ga")
    offer = create_offer(slug="stale-payment")
    payment = create_payment_transaction(
        idempotency_key="stale-payment",
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
    )
    stale = PaymentTransaction.objects.get(pk=payment.pk)
    payment.mark_succeeded(provider_reference="provider-stale")

    with pytest.raises(ValueError):
        stale.mark_failed(error_code="late_failure", message="Late failure callback")

    payment.refresh_from_db()
    assert payment.status == PaymentTransaction.Status.SUCCEEDED
    assert payment.failure_code == ""


@pytest.mark.django_db
def test_failed_payment_transaction_cannot_return_to_pending():
    user = create_user(email="failed-terminal@example.ga")
    offer = create_offer(slug="failed-terminal")
    payment = create_payment_transaction(
        idempotency_key="failed-terminal",
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
    )
    payment.mark_failed(error_code="provider_error", message="Provider failed")

    with pytest.raises(ValueError):
        payment.mark_pending(provider_reference="late-pending")

    payment.refresh_from_db()
    assert payment.status == PaymentTransaction.Status.FAILED


@pytest.mark.django_db
def test_cancelled_payment_transaction_cannot_be_marked_succeeded():
    user = create_user(email="cancelled-payment@example.ga")
    offer = create_offer(slug="cancelled-payment")
    payment = create_payment_transaction(
        idempotency_key="cancelled-to-success",
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
    )
    payment.status = PaymentTransaction.Status.CANCELLED
    payment.save(update_fields=["status", "updated_at"])

    with pytest.raises(ValueError):
        payment.mark_succeeded(provider_reference="provider-cancelled")

    payment.refresh_from_db()
    assert payment.status == PaymentTransaction.Status.CANCELLED
    assert payment.succeeded_at is None


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
