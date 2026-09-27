from __future__ import annotations

import pytest
from django.utils import timezone

from accounts.models import Entitlement, Organization, OrganizationMembership, User
from accounts.permissions import (
    administered_organization_ids,
    administers_organization,
    can_manage_organization_members,
    can_view_organization_reports,
)
from accounts.services import user_has_entitlement


def make_org(slug: str, *, requires_verification: bool = False) -> Organization:
    return Organization.objects.create(
        name=slug.upper(),
        slug=slug,
        organization_type=Organization.OrganizationType.UNIVERSITY,
        requires_identity_verification=requires_verification,
    )


def make_admin(email: str, *organizations, **membership) -> User:
    user = User.objects.create_user(
        email=email,
        password="passphrase",
        account_type=User.AccountType.ORGANIZATION_ADMIN,
    )
    for organization in organizations:
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=OrganizationMembership.Role.ADMIN,
            status=membership.get("status", OrganizationMembership.Status.ACTIVE),
            ends_at=membership.get("ends_at"),
            verification_status=membership.get(
                "verification_status", OrganizationMembership.VerificationStatus.UNVERIFIED
            ),
            verification_method=membership.get("verification_method", ""),
            verified_at=membership.get("verified_at"),
        )
    return user


@pytest.mark.django_db
def test_an_admin_of_one_organization_is_refused_on_another():
    uob, ustm = make_org("uob"), make_org("ustm")
    admin = make_admin("admin@uob.ga", uob)

    assert administers_organization(admin, uob) is True
    assert administers_organization(admin, ustm) is False
    assert can_manage_organization_members(admin, ustm) is False
    assert can_view_organization_reports(admin, ustm) is False


@pytest.mark.django_db
def test_an_admin_of_two_organizations_is_accepted_on_both():
    uob, ustm = make_org("uob"), make_org("ustm")
    admin = make_admin("admin@deux.ga", uob, ustm)

    assert administers_organization(admin, uob) is True
    assert administers_organization(admin, ustm) is True
    assert sorted(administered_organization_ids(admin)) == sorted([uob.pk, ustm.pk])


@pytest.mark.django_db
def test_a_suspended_membership_removes_administrative_authority():
    uob = make_org("uob")
    admin = make_admin("suspendu@uob.ga", uob, status=OrganizationMembership.Status.SUSPENDED)

    assert administers_organization(admin, uob) is False
    assert administered_organization_ids(admin) == []


@pytest.mark.django_db
def test_an_ended_membership_removes_administrative_authority():
    uob = make_org("uob")
    admin = make_admin("parti@uob.ga", uob, ends_at=timezone.now() - timezone.timedelta(days=1))

    assert administers_organization(admin, uob) is False


@pytest.mark.django_db
def test_an_unverified_identity_removes_authority_when_the_organization_requires_proof():
    """La même règle que pour la lecture : une université qui exige une
    preuve n'ouvre rien à une adhésion non vérifiée, fût-elle administrative."""
    uob = make_org("uob", requires_verification=True)
    admin = make_admin("non-verifie@uob.ga", uob)

    assert administers_organization(admin, uob) is False


@pytest.mark.django_db
def test_a_verified_identity_restores_authority():
    uob = make_org("uob", requires_verification=True)
    admin = make_admin(
        "verifie@uob.ga",
        uob,
        verification_status=OrganizationMembership.VerificationStatus.VERIFIED,
        verification_method=OrganizationMembership.VerificationMethod.STAFF_ID,
        verified_at=timezone.now(),
    )

    assert administers_organization(admin, uob) is True


@pytest.mark.django_db
def test_losing_administrative_authority_leaves_the_account_usable_as_a_reader():
    """Perdre l'autorité n'est pas perdre le compte : le document produit
    exige que le retrait d'une organisation ne supprime pas l'utilisateur."""
    uob = make_org("uob")
    admin = make_admin("ancien@uob.ga", uob, status=OrganizationMembership.Status.SUSPENDED)
    Entitlement.objects.create(
        user=admin,
        source=Entitlement.Source.ADMIN_GRANT,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(days=1),
    )

    assert administers_organization(admin, uob) is False
    assert admin.is_active is True
    assert user_has_entitlement(admin, Entitlement.AccessRight.READ) is True


@pytest.mark.django_db
def test_an_archived_organization_grants_no_authority():
    uob = make_org("uob")
    admin = make_admin("admin@uob.ga", uob)
    uob.status = Organization.Status.ARCHIVED
    uob.save(update_fields=["status"])

    assert administers_organization(admin, uob) is False
