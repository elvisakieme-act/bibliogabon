from __future__ import annotations

import pytest

from accounts.models import Entitlement, Organization, OrganizationMembership, User
from accounts.services import (
    add_organization_member,
    end_organization_membership,
    grant_entitlement,
    suspend_organization_membership,
)
from operations.models import AuditLog


@pytest.fixture
def organization(db) -> Organization:
    return Organization.objects.create(name="UOB", slug="uob")


@pytest.fixture
def actor(db) -> User:
    return User.objects.create_user(
        email="admin@uob.ga",
        password="p",
        account_type=User.AccountType.ORGANIZATION_ADMIN,
    )


@pytest.fixture
def member(db) -> User:
    return User.objects.create_user(
        email="etudiant@example.ga",
        password="p",
        account_type=User.AccountType.INDIVIDUAL,
    )


def last_event() -> AuditLog:
    return AuditLog.objects.order_by("-created_at", "-id").first()


@pytest.mark.django_db
def test_adding_a_member_records_an_audit_event(organization, actor, member):
    membership = add_organization_member(organization=organization, user=member, actor=actor)

    assert membership.status == OrganizationMembership.Status.ACTIVE
    event = last_event()
    assert event.event_type == "organization_member_added"
    assert event.actor_id == actor.pk
    assert event.metadata["organization_id"] == organization.pk
    assert event.metadata["member_id"] == member.pk


@pytest.mark.django_db
def test_suspending_a_member_records_an_audit_event(organization, actor, member):
    membership = add_organization_member(organization=organization, user=member, actor=actor)

    suspend_organization_membership(membership=membership, actor=actor, reason="Impayé")

    membership.refresh_from_db()
    assert membership.status == OrganizationMembership.Status.SUSPENDED
    event = last_event()
    assert event.event_type == "organization_member_suspended"
    assert event.metadata["reason"] == "Impayé"


@pytest.mark.django_db
def test_removing_a_member_ends_the_membership_without_deleting_the_account(
    organization, actor, member
):
    """« Le retrait d'une organisation arrête l'accès qu'elle accordait mais
    ne doit pas supprimer le compte utilisateur. »"""
    membership = add_organization_member(organization=organization, user=member, actor=actor)

    end_organization_membership(membership=membership, actor=actor, reason="Diplômé")

    membership.refresh_from_db()
    member.refresh_from_db()
    assert membership.status == OrganizationMembership.Status.ENDED
    assert membership.ends_at is not None
    assert User.objects.filter(pk=member.pk).exists()
    assert member.is_active is True
    assert last_event().event_type == "organization_member_ended"


@pytest.mark.django_db
def test_an_ended_membership_stops_granting_organization_access(organization, actor, member):
    from accounts.services import active_organization_ids_for_user

    membership = add_organization_member(organization=organization, user=member, actor=actor)
    assert active_organization_ids_for_user(member) == [organization.pk]

    end_organization_membership(membership=membership, actor=actor)

    assert active_organization_ids_for_user(member) == []


@pytest.mark.django_db
def test_an_admin_grant_is_audited(actor, member):
    """« Les administrateurs plateforme ne peuvent outrepasser un accès que
    par des actions administratives auditables. »"""
    entitlement = grant_entitlement(
        user=member,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        actor=actor,
        reason="Accès accordé au titre du pilote UOB",
    )

    assert entitlement.source == Entitlement.Source.ADMIN_GRANT
    event = last_event()
    assert event.event_type == "entitlement_granted"
    assert event.actor_id == actor.pk
    assert event.metadata["entitlement_id"] == entitlement.pk
    assert event.metadata["reason"] == "Accès accordé au titre du pilote UOB"


@pytest.mark.django_db
def test_a_grant_without_a_reason_is_refused(member):
    """Une dérogation sans motif n'est pas auditable."""
    with pytest.raises(ValueError):
        grant_entitlement(
            user=member,
            access_right=Entitlement.AccessRight.READ,
            scope_type=Entitlement.ScopeType.GLOBAL,
            reason="   ",
        )


@pytest.mark.django_db
def test_adding_an_existing_member_is_idempotent(organization, actor, member):
    first = add_organization_member(organization=organization, user=member, actor=actor)
    before = AuditLog.objects.count()

    second = add_organization_member(organization=organization, user=member, actor=actor)

    assert second.pk == first.pk
    assert AuditLog.objects.count() == before, "un non-changement ne s'audite pas"
