import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Entitlement, Organization, OrganizationMembership
from accounts.services import user_has_entitlement
from billing.models import CommercialOffer, OrganizationQuota, Subscription
from billing.services import activate_organization_quota, activate_subscription


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
