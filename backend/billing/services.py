from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
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

    defaults = {
        "user": user,
        "organization": organization,
        "offer": offer,
        "subscription": subscription,
        "provider": provider,
        "amount_xaf": amount_xaf,
        "provider_reference": provider_reference,
        "metadata": metadata or {},
    }
    with transaction.atomic():
        try:
            payment, _ = PaymentTransaction.objects.select_for_update().get_or_create(
                idempotency_key=idempotency_key,
                defaults=defaults,
            )
        except (IntegrityError, ValidationError) as exc:
            try:
                payment = PaymentTransaction.objects.select_for_update().get(
                    idempotency_key=idempotency_key
                )
            except PaymentTransaction.DoesNotExist:
                raise exc

        if _payment_terms(payment) != desired_terms:
            raise ValueError("idempotency_key already used for different payment terms")
        return payment


def _ensure_active_offer(offer: CommercialOffer):
    if not offer.is_active:
        raise ValueError("commercial offer is not active")


def _ensure_subscription_matches_offer_duration(subscription: Subscription):
    expected_ends_at = subscription.starts_at + timezone.timedelta(
        days=subscription.offer.duration_days
    )
    if subscription.ends_at != expected_ends_at:
        raise ValueError("subscription window must match offer duration")


def _subscription_note(subscription: Subscription) -> str:
    return f"subscription:{subscription.pk}"


def _organization_quota_note(quota: OrganizationQuota) -> str:
    return f"organization_quota:{quota.pk}"


def _revoke_entitlement(entitlement: Entitlement | None, *, at):
    if entitlement is None or entitlement.revoked_at is not None:
        return
    entitlement.revoked_at = at
    entitlement.save(update_fields=["revoked_at", "updated_at"])


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
        _ensure_subscription_matches_offer_duration(subscription)
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
                note=_subscription_note(subscription),
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
                note=_subscription_note(subscription),
            )

        subscription.status = Subscription.Status.ACTIVE
        subscription.entitlement = entitlement
        subscription.save(update_fields=["status", "entitlement", "updated_at"])
        return entitlement


def _close_subscription(*, subscription: Subscription, status: str, at=None) -> Subscription:
    at = at or timezone.now()
    with transaction.atomic():
        subscription = (
            Subscription.objects.select_for_update()
            .select_related("entitlement")
            .get(pk=subscription.pk)
        )
        subscription.status = status
        _revoke_entitlement(subscription.entitlement, at=at)
        subscription.save(update_fields=["status", "updated_at"])
        return subscription


def cancel_subscription(*, subscription: Subscription, at=None) -> Subscription:
    return _close_subscription(
        subscription=subscription,
        status=Subscription.Status.CANCELLED,
        at=at,
    )


def expire_subscription(*, subscription: Subscription, at=None) -> Subscription:
    return _close_subscription(
        subscription=subscription,
        status=Subscription.Status.EXPIRED,
        at=at,
    )


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
            note=_organization_quota_note(quota),
        )
        quota.status = OrganizationQuota.Status.ACTIVE
        quota.entitlement = entitlement
        quota.save(update_fields=["status", "entitlement", "updated_at"])
        return entitlement


def _close_organization_quota(*, quota: OrganizationQuota, status: str, at=None) -> OrganizationQuota:
    at = at or timezone.now()
    with transaction.atomic():
        quota = (
            OrganizationQuota.objects.select_for_update()
            .select_related("entitlement")
            .get(pk=quota.pk)
        )
        quota.status = status
        _revoke_entitlement(quota.entitlement, at=at)
        quota.save(update_fields=["status", "updated_at"])
        return quota


def suspend_organization_quota(*, quota: OrganizationQuota, at=None) -> OrganizationQuota:
    return _close_organization_quota(
        quota=quota,
        status=OrganizationQuota.Status.SUSPENDED,
        at=at,
    )


def cancel_organization_quota(*, quota: OrganizationQuota, at=None) -> OrganizationQuota:
    return _close_organization_quota(
        quota=quota,
        status=OrganizationQuota.Status.CANCELLED,
        at=at,
    )


def expire_organization_quota(*, quota: OrganizationQuota, at=None) -> OrganizationQuota:
    return _close_organization_quota(
        quota=quota,
        status=OrganizationQuota.Status.EXPIRED,
        at=at,
    )


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


def _close_sponsored_campaign(*, campaign: SponsoredCampaign, status: str, at=None) -> SponsoredCampaign:
    at = at or timezone.now()
    with transaction.atomic():
        campaign = SponsoredCampaign.objects.select_for_update().get(pk=campaign.pk)
        campaign.status = status
        Entitlement.objects.filter(
            source=Entitlement.Source.SPONSORED_CAMPAIGN,
            note=_campaign_note(campaign),
            revoked_at__isnull=True,
        ).update(revoked_at=at, updated_at=at)
        campaign.save(update_fields=["status", "updated_at"])
        return campaign


def end_sponsored_campaign(*, campaign: SponsoredCampaign, at=None) -> SponsoredCampaign:
    return _close_sponsored_campaign(
        campaign=campaign,
        status=SponsoredCampaign.Status.ENDED,
        at=at,
    )


def cancel_sponsored_campaign(*, campaign: SponsoredCampaign, at=None) -> SponsoredCampaign:
    return _close_sponsored_campaign(
        campaign=campaign,
        status=SponsoredCampaign.Status.CANCELLED,
        at=at,
    )
