import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from accounts.models import Organization, OrganizationMembership


@pytest.mark.django_db
def test_create_organization_and_active_membership():
    User = get_user_model()
    user = User.objects.create_user(email="student@example.ga", password="pass")
    organization = Organization.objects.create(
        name="Universite Omar Bongo",
        slug="uob",
        organization_type=Organization.OrganizationType.UNIVERSITY,
    )

    membership = OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=OrganizationMembership.Role.MEMBER,
        status=OrganizationMembership.Status.ACTIVE,
    )

    assert str(organization) == "Universite Omar Bongo"
    assert membership.is_active is True
    assert str(membership) == "student@example.ga @ Universite Omar Bongo"


@pytest.mark.django_db
def test_user_can_have_only_one_membership_record_per_organization():
    User = get_user_model()
    user = User.objects.create_user(email="student@example.ga", password="pass")
    organization = Organization.objects.create(name="USTM", slug="ustm")

    OrganizationMembership.objects.create(organization=organization, user=user)

    with pytest.raises(IntegrityError):
        OrganizationMembership.objects.create(organization=organization, user=user)
