from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from accounts.models import Entitlement
from billing.models import CommercialOffer, PaymentTransaction, Subscription
from billing.models import OrganizationQuota, SponsoredCampaign


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


def _ensure_active_offer(offer: CommercialOffer):
    if not offer.is_active:
        raise ValueError("commercial offer is not active")


def _entitlement_defaults(*, offer: CommercialOffer, starts_at, ends_at) -> dict:
    return {
        "source": Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        "access_right": offer.access_right,
        "scope_type": offer.scope_type,
        "scope_id": offer.scope_id,
        "starts_at": starts_at,
        "ends_at": ends_at,
    }


def activate_subscription(*, subscription: Subscription, at=None) -> Entitlement:
    with transaction.atomic():
        subscription = (
            Subscription.objects.select_for_update()
            .select_related("offer", "user", "organization", "entitlement")
            .get(pk=subscription.pk)
        )
        if subscription.status in {Subscription.Status.CANCELLED, Subscription.Status.EXPIRED}:
            raise ValueError("subscription cannot be activated")
        _ensure_active_offer(subscription.offer)
        if subscription.entitlement_id:
            return subscription.entitlement

        defaults = _entitlement_defaults(
            offer=subscription.offer,
            starts_at=subscription.starts_at,
            ends_at=subscription.ends_at,
        )
        if subscription.user_id:
            entitlement, _ = Entitlement.objects.get_or_create(
                user=subscription.user,
                organization=None,
                source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
                access_right=defaults["access_right"],
                scope_type=defaults["scope_type"],
                scope_id=defaults["scope_id"],
                starts_at=defaults["starts_at"],
                ends_at=defaults["ends_at"],
            )
        else:
            entitlement, _ = Entitlement.objects.get_or_create(
                user=None,
                organization=subscription.organization,
                source=Entitlement.Source.ORGANIZATION_QUOTA,
                access_right=defaults["access_right"],
                scope_type=defaults["scope_type"],
                scope_id=defaults["scope_id"],
                starts_at=defaults["starts_at"],
                ends_at=defaults["ends_at"],
            )

        subscription.status = Subscription.Status.ACTIVE
        subscription.entitlement = entitlement
        subscription.save(update_fields=["status", "entitlement", "updated_at"])
        return entitlement


def activate_organization_quota(*, quota: OrganizationQuota, at=None) -> Entitlement:
    with transaction.atomic():
        quota = (
            OrganizationQuota.objects.select_for_update()
            .select_related("organization", "offer", "entitlement")
            .get(pk=quota.pk)
        )
        if quota.status in {
            OrganizationQuota.Status.CANCELLED,
            OrganizationQuota.Status.SUSPENDED,
            OrganizationQuota.Status.EXPIRED,
        }:
            raise ValueError("organization quota cannot be activated")
        _ensure_active_offer(quota.offer)
        if quota.entitlement_id:
            return quota.entitlement

        entitlement, _ = Entitlement.objects.get_or_create(
            user=None,
            organization=quota.organization,
            source=Entitlement.Source.ORGANIZATION_QUOTA,
            access_right=quota.offer.access_right,
            scope_type=quota.offer.scope_type,
            scope_id=quota.offer.scope_id,
            starts_at=quota.starts_at,
            ends_at=quota.ends_at,
        )
        quota.status = OrganizationQuota.Status.ACTIVE
        quota.entitlement = entitlement
        quota.save(update_fields=["status", "entitlement", "updated_at"])
        return entitlement


def _campaign_note(campaign: SponsoredCampaign) -> str:
    return f"sponsored_campaign:{campaign.pk}"


def enroll_user_in_sponsored_campaign(*, campaign: SponsoredCampaign, user, at=None) -> Entitlement:
    at = at or timezone.now()
    with transaction.atomic():
        campaign = (
            SponsoredCampaign.objects.select_for_update()
            .select_related("sponsor")
            .get(pk=campaign.pk)
        )
        if campaign.status != SponsoredCampaign.Status.ACTIVE:
            raise ValueError("sponsored campaign is not active")
        if campaign.starts_at > at or campaign.ends_at <= at:
            raise ValueError("sponsored campaign is outside its active window")

        note = _campaign_note(campaign)
        existing = Entitlement.objects.filter(
            user=user,
            organization=None,
            source=Entitlement.Source.SPONSORED_CAMPAIGN,
            access_right=campaign.access_right,
            scope_type=campaign.scope_type,
            scope_id=campaign.scope_id,
            note=note,
        ).first()
        if existing:
            return existing

        enrolled_count = Entitlement.objects.filter(
            source=Entitlement.Source.SPONSORED_CAMPAIGN,
            note=note,
            revoked_at__isnull=True,
        ).count()
        if enrolled_count >= campaign.funded_seat_count:
            raise ValueError("sponsored campaign capacity is exhausted")

        return Entitlement.objects.create(
            user=user,
            organization=None,
            source=Entitlement.Source.SPONSORED_CAMPAIGN,
            access_right=campaign.access_right,
            scope_type=campaign.scope_type,
            scope_id=campaign.scope_id,
            starts_at=campaign.starts_at,
            ends_at=campaign.ends_at,
            note=note,
        )
