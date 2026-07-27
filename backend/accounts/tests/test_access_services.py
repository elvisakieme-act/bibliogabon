import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Entitlement, Organization, OrganizationMembership
from accounts.services import user_has_entitlement


@pytest.mark.django_db
def test_user_has_direct_read_entitlement():
    User = get_user_model()
    user = User.objects.create_user(email="reader@example.ga", password="pass")
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(hours=1),
        ends_at=timezone.now() + timezone.timedelta(hours=1),
    )

    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.django_db
def test_user_in_active_organization_inherits_organization_entitlement():
    User = get_user_model()
    user = User.objects.create_user(email="student@example.ga", password="pass")
    organization = Organization.objects.create(name="UOB", slug="uob")
    OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        status=OrganizationMembership.Status.ACTIVE,
    )
    Entitlement.objects.create(
        organization=organization,
        source=Entitlement.Source.ORGANIZATION_QUOTA,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(hours=1),
        ends_at=timezone.now() + timezone.timedelta(hours=1),
    )

    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.django_db
def test_download_requires_download_right_not_only_read_right():
    User = get_user_model()
    user = User.objects.create_user(email="reader@example.ga", password="pass")
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(hours=1),
        ends_at=timezone.now() + timezone.timedelta(hours=1),
    )

    assert user_has_entitlement(user, Entitlement.AccessRight.DOWNLOAD) is False
