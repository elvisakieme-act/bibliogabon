import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Entitlement, Organization
from billing.models import (
    CommercialOffer,
    OrganizationQuota,
    PaymentTransaction,
    SponsoredCampaign,
    Subscription,
)


def create_user(email="billing-user@example.ga"):
    return get_user_model().objects.create_user(email=email, password="pass")


def create_organization(slug="billing-org"):
    return Organization.objects.create(name=f"Organisation {slug}", slug=slug)


def create_offer(slug="monthly-pass", offer_type=None, scope_type=Entitlement.ScopeType.GLOBAL, scope_id=""):
    return CommercialOffer.objects.create(
        name=f"Offer {slug}",
        slug=slug,
        offer_type=offer_type or CommercialOffer.OfferType.INDIVIDUAL,
        billing_period=CommercialOffer.BillingPeriod.MONTHLY,
        price_xaf=2500,
        duration_days=30,
        access_right=Entitlement.AccessRight.READ,
        scope_type=scope_type,
        scope_id=scope_id,
    )


@pytest.mark.django_db
def test_commercial_offer_stores_access_terms():
    offer = create_offer(
        slug="domain-pass",
        scope_type=Entitlement.ScopeType.DOMAIN,
        scope_id="12",
    )

    assert str(offer) == "Offer domain-pass"
    assert offer.price_xaf == 2500
    assert offer.duration_days == 30
    assert offer.access_right == Entitlement.AccessRight.READ
    assert offer.scope_type == Entitlement.ScopeType.DOMAIN
    assert offer.scope_id == "12"
    assert offer.is_active is True


@pytest.mark.parametrize(
    ("price_xaf", "duration_days", "access_right", "scope_type", "scope_id"),
    [
        (-1, 30, Entitlement.AccessRight.READ, Entitlement.ScopeType.GLOBAL, ""),
        (1000, 0, Entitlement.AccessRight.READ, Entitlement.ScopeType.GLOBAL, ""),
        (1000, 30, "stream", Entitlement.ScopeType.GLOBAL, ""),
        (1000, 30, Entitlement.AccessRight.READ, Entitlement.ScopeType.DOCUMENT, ""),
    ],
)
@pytest.mark.django_db
def test_commercial_offer_rejects_invalid_terms(
    price_xaf,
    duration_days,
    access_right,
    scope_type,
    scope_id,
):
    offer = CommercialOffer(
        name="Invalid offer",
        slug=f"invalid-{price_xaf}-{duration_days}-{access_right}-{scope_type}",
        offer_type=CommercialOffer.OfferType.INDIVIDUAL,
        billing_period=CommercialOffer.BillingPeriod.MONTHLY,
        price_xaf=price_xaf,
        duration_days=duration_days,
        access_right=access_right,
        scope_type=scope_type,
        scope_id=scope_id,
    )

    with pytest.raises(ValidationError):
        offer.save()


@pytest.mark.django_db
def test_subscription_targets_exactly_one_user_or_organization():
    offer = create_offer()
    user = create_user()
    organization = create_organization()
    starts_at = timezone.now()
    ends_at = starts_at + timezone.timedelta(days=30)

    user_subscription = Subscription.objects.create(
        offer=offer,
        user=user,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    assert user_subscription.user == user
    assert user_subscription.organization is None
    with pytest.raises(ValidationError):
        Subscription(
            offer=offer,
            user=user,
            organization=organization,
            starts_at=starts_at,
            ends_at=ends_at,
        ).save()
    with pytest.raises(ValidationError):
        Subscription(offer=offer, starts_at=starts_at, ends_at=ends_at).save()


@pytest.mark.django_db
def test_subscription_rejects_invalid_date_window():
    offer = create_offer()
    user = create_user()
    starts_at = timezone.now()

    with pytest.raises(ValidationError):
        Subscription(
            offer=offer,
            user=user,
            starts_at=starts_at,
            ends_at=starts_at,
        ).save()


@pytest.mark.django_db
def test_payment_transaction_requires_unique_idempotency_key():
    user = create_user()
    offer = create_offer()
    PaymentTransaction.objects.create(
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
        idempotency_key="pay-unique-key",
    )

    duplicate = PaymentTransaction(
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        amount_xaf=2500,
        idempotency_key="pay-unique-key",
    )

    with pytest.raises(ValidationError):
        duplicate.save()


@pytest.mark.django_db
def test_organization_quota_stores_contract_capacity():
    offer = create_offer(slug="institution-license", offer_type=CommercialOffer.OfferType.ORGANIZATION)
    organization = create_organization(slug="quota-org")
    starts_at = timezone.now()
    quota = OrganizationQuota.objects.create(
        organization=organization,
        offer=offer,
        seat_limit=120,
        starts_at=starts_at,
        ends_at=starts_at + timezone.timedelta(days=365),
        contract_reference="UOB-2026-001",
    )

    assert quota.organization == organization
    assert quota.seat_limit == 120
    assert quota.contract_reference == "UOB-2026-001"
    assert quota.status == OrganizationQuota.Status.DRAFT


@pytest.mark.django_db
def test_sponsored_campaign_requires_positive_capacity_and_valid_dates():
    sponsor = create_organization(slug="sponsor-bank")
    starts_at = timezone.now()
    campaign = SponsoredCampaign.objects.create(
        sponsor=sponsor,
        name="Exam access",
        slug="exam-access",
        funded_seat_count=50,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=starts_at,
        ends_at=starts_at + timezone.timedelta(days=45),
    )

    assert campaign.sponsor == sponsor
    assert campaign.funded_seat_count == 50
    with pytest.raises(ValidationError):
        SponsoredCampaign(
            sponsor=sponsor,
            name="Invalid campaign",
            slug="invalid-campaign",
            funded_seat_count=0,
            access_right=Entitlement.AccessRight.READ,
            scope_type=Entitlement.ScopeType.GLOBAL,
            starts_at=starts_at,
            ends_at=starts_at + timezone.timedelta(days=45),
        ).save()
    with pytest.raises(ValidationError):
        SponsoredCampaign(
            sponsor=sponsor,
            name="Invalid dates",
            slug="invalid-dates",
            funded_seat_count=5,
            access_right=Entitlement.AccessRight.READ,
            scope_type=Entitlement.ScopeType.GLOBAL,
            starts_at=starts_at,
            ends_at=starts_at,
        ).save()
