import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Entitlement, Organization, OrganizationMembership
from accounts.services import user_has_entitlement
from billing.models import CommercialOffer, OrganizationQuota, SponsoredCampaign, Subscription
from billing.services import (
    activate_organization_quota,
    activate_subscription,
    cancel_subscription,
    end_sponsored_campaign,
    enroll_user_in_sponsored_campaign,
    expire_subscription,
    suspend_organization_quota,
)


def create_user(email="access-user@example.ga"):
    return get_user_model().objects.create_user(email=email, password="pass")


def create_organization(slug="access-org"):
    return Organization.objects.create(name=f"Organisation {slug}", slug=slug)


def create_offer(slug="access-offer", offer_type=CommercialOffer.OfferType.INDIVIDUAL, is_active=True):
    return CommercialOffer.objects.create(
        name=f"Access offer {slug}",
        slug=slug,
        offer_type=offer_type,
        billing_period=CommercialOffer.BillingPeriod.MONTHLY,
        price_xaf=2500,
        duration_days=30,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        is_active=is_active,
    )


def subscription_window():
    starts_at = timezone.now()
    return starts_at, starts_at + timezone.timedelta(days=30)


@pytest.mark.django_db
def test_activate_individual_subscription_creates_user_entitlement_once():
    user = create_user()
    offer = create_offer()
    starts_at, ends_at = subscription_window()
    subscription = Subscription.objects.create(
        offer=offer,
        user=user,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    entitlement = activate_subscription(subscription=subscription)
    repeated = activate_subscription(subscription=subscription)

    subscription.refresh_from_db()
    assert repeated.pk == entitlement.pk
    assert Entitlement.objects.count() == 1
    assert subscription.status == Subscription.Status.ACTIVE
    assert subscription.entitlement == entitlement
    assert entitlement.user == user
    assert entitlement.organization is None
    assert entitlement.source == Entitlement.Source.INDIVIDUAL_SUBSCRIPTION
    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.django_db
def test_cancel_subscription_revokes_existing_user_entitlement():
    user = create_user(email="cancelled-user@example.ga")
    offer = create_offer(slug="cancelled-subscription")
    starts_at, ends_at = subscription_window()
    subscription = Subscription.objects.create(
        offer=offer,
        user=user,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    entitlement = activate_subscription(subscription=subscription)

    cancelled = cancel_subscription(subscription=subscription)

    entitlement.refresh_from_db()
    assert cancelled.status == Subscription.Status.CANCELLED
    assert entitlement.revoked_at is not None
    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is False


@pytest.mark.django_db
def test_cancel_subscription_does_not_revoke_another_matching_subscription_entitlement():
    user = create_user(email="parallel-subscriptions@example.ga")
    offer = create_offer(slug="parallel-subscriptions")
    starts_at, ends_at = subscription_window()
    first_subscription = Subscription.objects.create(
        offer=offer,
        user=user,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    second_subscription = Subscription.objects.create(
        offer=offer,
        user=user,
        starts_at=starts_at,
        ends_at=ends_at,
        external_reference="second",
    )
    first_entitlement = activate_subscription(subscription=first_subscription)
    second_entitlement = activate_subscription(subscription=second_subscription)

    cancel_subscription(subscription=first_subscription)

    first_entitlement.refresh_from_db()
    second_entitlement.refresh_from_db()
    assert first_entitlement.pk != second_entitlement.pk
    assert first_entitlement.revoked_at is not None
    assert second_entitlement.revoked_at is None
    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.django_db
def test_expire_subscription_revokes_existing_user_entitlement():
    user = create_user(email="expired-user@example.ga")
    offer = create_offer(slug="expired-subscription")
    starts_at, ends_at = subscription_window()
    subscription = Subscription.objects.create(
        offer=offer,
        user=user,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    entitlement = activate_subscription(subscription=subscription)

    expired = expire_subscription(subscription=subscription)

    entitlement.refresh_from_db()
    assert expired.status == Subscription.Status.EXPIRED
    assert entitlement.revoked_at is not None
    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is False


@pytest.mark.django_db
def test_activate_organization_subscription_creates_organization_entitlement():
    organization = create_organization(slug="subscriber-org")
    user = create_user(email="member@example.ga")
    OrganizationMembership.objects.create(organization=organization, user=user)
    offer = create_offer(slug="org-subscription", offer_type=CommercialOffer.OfferType.ORGANIZATION)
    starts_at, ends_at = subscription_window()
    subscription = Subscription.objects.create(
        offer=offer,
        organization=organization,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    entitlement = activate_subscription(subscription=subscription)

    assert entitlement.organization == organization
    assert entitlement.user is None
    assert entitlement.source == Entitlement.Source.ORGANIZATION_QUOTA
    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.parametrize("status", [Subscription.Status.CANCELLED, Subscription.Status.EXPIRED])
@pytest.mark.django_db
def test_activate_subscription_rejects_closed_subscription(status):
    user = create_user()
    offer = create_offer(slug=f"closed-{status}")
    starts_at, ends_at = subscription_window()
    subscription = Subscription.objects.create(
        offer=offer,
        user=user,
        status=status,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    with pytest.raises(ValueError):
        activate_subscription(subscription=subscription)

    assert Entitlement.objects.count() == 0


@pytest.mark.django_db
def test_activate_subscription_rejects_inactive_offer():
    user = create_user()
    offer = create_offer(slug="inactive-offer", is_active=False)
    starts_at, ends_at = subscription_window()
    subscription = Subscription.objects.create(
        offer=offer,
        user=user,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    with pytest.raises(ValueError):
        activate_subscription(subscription=subscription)

    assert Entitlement.objects.count() == 0


@pytest.mark.django_db
def test_activate_subscription_rejects_entitlement_window_that_exceeds_offer_duration():
    user = create_user(email="long-window@example.ga")
    offer = create_offer(slug="thirty-day-offer")
    starts_at = timezone.now()
    subscription = Subscription.objects.create(
        offer=offer,
        user=user,
        starts_at=starts_at,
        ends_at=starts_at + timezone.timedelta(days=365),
    )

    with pytest.raises(ValueError):
        activate_subscription(subscription=subscription)

    assert Entitlement.objects.count() == 0


@pytest.mark.django_db
def test_activate_organization_quota_creates_organization_entitlement_once():
    organization = create_organization(slug="quota-activation")
    user = create_user(email="quota-member@example.ga")
    OrganizationMembership.objects.create(organization=organization, user=user)
    offer = create_offer(slug="quota-offer", offer_type=CommercialOffer.OfferType.ORGANIZATION)
    starts_at, ends_at = subscription_window()
    quota = OrganizationQuota.objects.create(
        organization=organization,
        offer=offer,
        seat_limit=25,
        starts_at=starts_at,
        ends_at=ends_at,
        contract_reference="CONTRACT-2026",
    )

    entitlement = activate_organization_quota(quota=quota)
    repeated = activate_organization_quota(quota=quota)

    quota.refresh_from_db()
    assert repeated.pk == entitlement.pk
    assert Entitlement.objects.count() == 1
    assert quota.status == OrganizationQuota.Status.ACTIVE
    assert quota.entitlement == entitlement
    assert entitlement.organization == organization
    assert entitlement.source == Entitlement.Source.ORGANIZATION_QUOTA
    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.django_db
def test_suspend_organization_quota_revokes_existing_organization_entitlement():
    organization = create_organization(slug="suspended-quota")
    user = create_user(email="suspended-member@example.ga")
    OrganizationMembership.objects.create(organization=organization, user=user)
    offer = create_offer(slug="suspended-quota-offer", offer_type=CommercialOffer.OfferType.ORGANIZATION)
    starts_at, ends_at = subscription_window()
    quota = OrganizationQuota.objects.create(
        organization=organization,
        offer=offer,
        seat_limit=25,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    entitlement = activate_organization_quota(quota=quota)

    suspended = suspend_organization_quota(quota=quota)

    entitlement.refresh_from_db()
    assert suspended.status == OrganizationQuota.Status.SUSPENDED
    assert entitlement.revoked_at is not None
    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is False


@pytest.mark.django_db
def test_suspend_organization_quota_does_not_revoke_another_matching_quota_entitlement():
    organization = create_organization(slug="parallel-quotas")
    user = create_user(email="parallel-quota-member@example.ga")
    OrganizationMembership.objects.create(organization=organization, user=user)
    offer = create_offer(slug="parallel-quota-offer", offer_type=CommercialOffer.OfferType.ORGANIZATION)
    starts_at, ends_at = subscription_window()
    first_quota = OrganizationQuota.objects.create(
        organization=organization,
        offer=offer,
        seat_limit=25,
        starts_at=starts_at,
        ends_at=ends_at,
        contract_reference="first",
    )
    second_quota = OrganizationQuota.objects.create(
        organization=organization,
        offer=offer,
        seat_limit=25,
        starts_at=starts_at,
        ends_at=ends_at,
        contract_reference="second",
    )
    first_entitlement = activate_organization_quota(quota=first_quota)
    second_entitlement = activate_organization_quota(quota=second_quota)

    suspend_organization_quota(quota=first_quota)

    first_entitlement.refresh_from_db()
    second_entitlement.refresh_from_db()
    assert first_entitlement.pk != second_entitlement.pk
    assert first_entitlement.revoked_at is not None
    assert second_entitlement.revoked_at is None
    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.parametrize(
    "status",
    [
        OrganizationQuota.Status.CANCELLED,
        OrganizationQuota.Status.SUSPENDED,
        OrganizationQuota.Status.EXPIRED,
    ],
)
@pytest.mark.django_db
def test_activate_organization_quota_rejects_closed_or_suspended_quota(status):
    organization = create_organization(slug=f"closed-quota-{status}")
    offer = create_offer(slug=f"closed-quota-offer-{status}", offer_type=CommercialOffer.OfferType.ORGANIZATION)
    starts_at, ends_at = subscription_window()
    quota = OrganizationQuota.objects.create(
        organization=organization,
        offer=offer,
        status=status,
        seat_limit=10,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    with pytest.raises(ValueError):
        activate_organization_quota(quota=quota)

    assert Entitlement.objects.count() == 0


def create_campaign(slug="sponsored-access", status=SponsoredCampaign.Status.ACTIVE, funded_seat_count=2):
    sponsor = create_organization(slug=f"sponsor-{slug}")
    starts_at = timezone.now() - timezone.timedelta(minutes=5)
    return SponsoredCampaign.objects.create(
        sponsor=sponsor,
        name=f"Campaign {slug}",
        slug=slug,
        status=status,
        funded_seat_count=funded_seat_count,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=starts_at,
        ends_at=starts_at + timezone.timedelta(days=30),
    )


@pytest.mark.django_db
def test_enroll_user_in_sponsored_campaign_creates_user_entitlement_once():
    campaign = create_campaign()
    user = create_user(email="sponsored-user@example.ga")

    entitlement = enroll_user_in_sponsored_campaign(campaign=campaign, user=user)
    repeated = enroll_user_in_sponsored_campaign(campaign=campaign, user=user)

    assert repeated.pk == entitlement.pk
    assert Entitlement.objects.count() == 1
    assert entitlement.user == user
    assert entitlement.organization is None
    assert entitlement.source == Entitlement.Source.SPONSORED_CAMPAIGN
    assert entitlement.starts_at == campaign.starts_at
    assert entitlement.ends_at == campaign.ends_at
    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.django_db
def test_enroll_user_in_sponsored_campaign_ignores_revoked_entitlement():
    campaign = create_campaign(slug="revoked-sponsored-access")
    user = create_user(email="revoked-sponsored-user@example.ga")
    revoked_at = timezone.now()
    first_entitlement = enroll_user_in_sponsored_campaign(campaign=campaign, user=user)
    first_entitlement.revoked_at = revoked_at
    first_entitlement.save(update_fields=["revoked_at", "updated_at"])

    second_entitlement = enroll_user_in_sponsored_campaign(campaign=campaign, user=user)

    first_entitlement.refresh_from_db()
    assert second_entitlement.pk != first_entitlement.pk
    assert first_entitlement.revoked_at == revoked_at
    assert second_entitlement.revoked_at is None
    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.django_db
def test_enroll_user_in_sponsored_campaign_rejects_when_capacity_is_exhausted():
    campaign = create_campaign(slug="limited-campaign", funded_seat_count=1)
    first_user = create_user(email="first-sponsored@example.ga")
    second_user = create_user(email="second-sponsored@example.ga")
    enroll_user_in_sponsored_campaign(campaign=campaign, user=first_user)

    with pytest.raises(ValueError):
        enroll_user_in_sponsored_campaign(campaign=campaign, user=second_user)

    assert Entitlement.objects.count() == 1


@pytest.mark.parametrize(
    "status",
    [
        SponsoredCampaign.Status.DRAFT,
        SponsoredCampaign.Status.ENDED,
        SponsoredCampaign.Status.CANCELLED,
    ],
)
@pytest.mark.django_db
def test_enroll_user_in_sponsored_campaign_rejects_inactive_campaign_status(status):
    campaign = create_campaign(slug=f"inactive-campaign-{status}", status=status)
    user = create_user(email=f"{status}@example.ga")

    with pytest.raises(ValueError):
        enroll_user_in_sponsored_campaign(campaign=campaign, user=user)

    assert Entitlement.objects.count() == 0


@pytest.mark.django_db
def test_end_sponsored_campaign_revokes_enrolled_user_entitlements():
    campaign = create_campaign(slug="ending-campaign", funded_seat_count=2)
    first_user = create_user(email="ending-first@example.ga")
    second_user = create_user(email="ending-second@example.ga")
    first_entitlement = enroll_user_in_sponsored_campaign(campaign=campaign, user=first_user)
    second_entitlement = enroll_user_in_sponsored_campaign(campaign=campaign, user=second_user)

    ended = end_sponsored_campaign(campaign=campaign)

    first_entitlement.refresh_from_db()
    second_entitlement.refresh_from_db()
    assert ended.status == SponsoredCampaign.Status.ENDED
    assert first_entitlement.revoked_at is not None
    assert second_entitlement.revoked_at is not None
    assert user_has_entitlement(first_user, Entitlement.AccessRight.READ) is False
    assert user_has_entitlement(second_user, Entitlement.AccessRight.READ) is False
