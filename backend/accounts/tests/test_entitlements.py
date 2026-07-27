import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Entitlement


@pytest.mark.django_db
def test_direct_entitlement_is_active_inside_valid_window():
    User = get_user_model()
    user = User.objects.create_user(email="reader@example.ga", password="pass")
    entitlement = Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(days=1),
        ends_at=timezone.now() + timezone.timedelta(days=1),
    )

    assert entitlement.is_active_at(timezone.now()) is True


@pytest.mark.django_db
def test_expired_entitlement_is_inactive():
    User = get_user_model()
    user = User.objects.create_user(email="reader@example.ga", password="pass")
    entitlement = Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(days=3),
        ends_at=timezone.now() - timezone.timedelta(days=1),
    )

    assert entitlement.is_active_at(timezone.now()) is False
