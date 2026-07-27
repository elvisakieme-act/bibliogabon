from django.contrib import admin

from billing.models import (
    CommercialOffer,
    OrganizationQuota,
    PaymentTransaction,
    SponsoredCampaign,
    Subscription,
)


def test_billing_models_are_registered_in_admin():
    assert CommercialOffer in admin.site._registry
    assert Subscription in admin.site._registry
    assert PaymentTransaction in admin.site._registry
    assert OrganizationQuota in admin.site._registry
    assert SponsoredCampaign in admin.site._registry
