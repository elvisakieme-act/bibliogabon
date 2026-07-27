from django.contrib import admin

from accounts.models import Entitlement, Organization, OrganizationMembership, User


def test_core_identity_models_are_registered_in_admin():
    assert User in admin.site._registry
    assert Organization in admin.site._registry
    assert OrganizationMembership in admin.site._registry
    assert Entitlement in admin.site._registry
