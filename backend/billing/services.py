from __future__ import annotations

from django.db import transaction

from billing.models import CommercialOffer, PaymentTransaction, Subscription


def _pk(value):
    return value.pk if value is not None else None


def _payment_terms(payment: PaymentTransaction) -> dict:
    return {
        "user_id": payment.user_id,
        "organization_id": payment.organization_id,
        "offer_id": payment.offer_id,
        "subscription_id": payment.subscription_id,
        "provider": payment.provider,
        "amount_xaf": payment.amount_xaf,
    }


def create_payment_transaction(
    *,
    idempotency_key: str,
    amount_xaf: int,
    provider: str,
    user=None,
    organization=None,
    offer: CommercialOffer | None = None,
    subscription: Subscription | None = None,
    provider_reference: str = "",
    metadata: dict | None = None,
) -> PaymentTransaction:
    desired_terms = {
        "user_id": _pk(user),
        "organization_id": _pk(organization),
        "offer_id": _pk(offer),
        "subscription_id": _pk(subscription),
        "provider": provider,
        "amount_xaf": amount_xaf,
    }

    with transaction.atomic():
        try:
            payment = PaymentTransaction.objects.select_for_update().get(
                idempotency_key=idempotency_key
            )
        except PaymentTransaction.DoesNotExist:
            return PaymentTransaction.objects.create(
                user=user,
                organization=organization,
                offer=offer,
                subscription=subscription,
                provider=provider,
                amount_xaf=amount_xaf,
                idempotency_key=idempotency_key,
                provider_reference=provider_reference,
                metadata=metadata or {},
            )

        if _payment_terms(payment) != desired_terms:
            raise ValueError("idempotency_key already used for different payment terms")
        return payment
