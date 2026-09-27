from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from accounts.models import Entitlement, Organization, OrganizationMembership, User


def active_organization_ids_for_user(user: User, at=None) -> list[int]:
    at = at or timezone.now()
    memberships = (
        OrganizationMembership.objects.filter(
            user=user,
            status=OrganizationMembership.Status.ACTIVE,
            starts_at__lte=at,
            organization__status=Organization.Status.ACTIVE,
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))
        .filter(
            # Une organisation qui exige une preuve d'identité n'ouvre l'accès
            # qu'aux adhésions dont l'identité a été vérifiée.
            Q(organization__requires_identity_verification=False)
            | Q(verification_status=OrganizationMembership.VerificationStatus.VERIFIED)
        )
    )

    return list(memberships.values_list("organization_id", flat=True))


def user_has_entitlement(
    user: User,
    access_right: str,
    scope_type: str = Entitlement.ScopeType.GLOBAL,
    scope_id: str = "",
    at=None,
) -> bool:
    at = at or timezone.now()
    organization_ids = active_organization_ids_for_user(user, at=at)
    candidates = Entitlement.objects.filter(
        Q(user=user) | Q(user__isnull=True, organization_id__in=organization_ids),
        access_right=access_right,
        starts_at__lte=at,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))

    for entitlement in candidates:
        if entitlement.is_active_at(at) and entitlement.matches_scope(scope_type, scope_id):
            return True
    return False


# --- Actions portées par un rôle, donc auditées ------------------------------
#
# « Les administrateurs plateforme ne peuvent outrepasser un accès que par des
# actions administratives auditables. » Ces fonctions sont le chemin par lequel
# l'admin et la future API modifient adhésions et dérogations : un `save()`
# direct reste possible, mais il ne laisse pas de trace, et c'est justement ce
# qu'on veut rendre visible.


def _audit(*, event_type: str, summary: str, actor=None, target=None, metadata=None):
    # Import différé : `operations` dépend de `accounts`, donc l'importer au
    # niveau du module inverserait la dépendance.
    from operations.services import record_audit_event

    return record_audit_event(
        actor=actor,
        event_type=event_type,
        target=target,
        summary=summary,
        metadata=metadata or {},
    )


def add_organization_member(
    *,
    organization: Organization,
    user: User,
    role: str = OrganizationMembership.Role.MEMBER,
    actor=None,
) -> OrganizationMembership:
    """Rattache un utilisateur à une organisation. Idempotent : réadhérer
    quelqu'un de déjà membre ne produit pas d'événement."""
    membership, created = OrganizationMembership.objects.get_or_create(
        organization=organization,
        user=user,
        defaults={"role": role, "status": OrganizationMembership.Status.ACTIVE},
    )
    if not created:
        return membership

    _audit(
        event_type="organization_member_added",
        summary=f"{user.email} rejoint {organization.name}",
        actor=actor,
        target=organization,
        metadata={
            "organization_id": organization.pk,
            "member_id": user.pk,
            "role": role,
        },
    )
    return membership


def suspend_organization_membership(
    *, membership: OrganizationMembership, actor=None, reason: str = ""
) -> OrganizationMembership:
    membership.status = OrganizationMembership.Status.SUSPENDED
    membership.save(update_fields=["status", "updated_at"])
    _audit(
        event_type="organization_member_suspended",
        summary=f"{membership.user.email} suspendu de {membership.organization.name}",
        actor=actor,
        target=membership.organization,
        metadata={
            "organization_id": membership.organization_id,
            "member_id": membership.user_id,
            "reason": reason,
        },
    )
    return membership


def end_organization_membership(
    *, membership: OrganizationMembership, actor=None, reason: str = "", at=None
) -> OrganizationMembership:
    """Met fin à une adhésion sans toucher au compte.

    Le retrait d'une organisation arrête l'accès qu'elle accordait ; il ne
    supprime ni l'utilisateur, ni son historique, ni ses autres accès.
    """
    at = at or timezone.now()
    membership.status = OrganizationMembership.Status.ENDED
    membership.ends_at = at
    membership.save(update_fields=["status", "ends_at", "updated_at"])
    _audit(
        event_type="organization_member_ended",
        summary=f"{membership.user.email} quitte {membership.organization.name}",
        actor=actor,
        target=membership.organization,
        metadata={
            "organization_id": membership.organization_id,
            "member_id": membership.user_id,
            "reason": reason,
        },
    )
    return membership


def grant_entitlement(
    *,
    access_right: str,
    scope_type: str = Entitlement.ScopeType.GLOBAL,
    scope_id: str = "",
    user: User | None = None,
    organization: Organization | None = None,
    actor=None,
    reason: str,
    starts_at=None,
    ends_at=None,
) -> Entitlement:
    """Dérogation administrative : accorde un accès hors parcours commercial.

    Le motif est obligatoire — une dérogation sans motif n'est pas auditable,
    et c'est la seule chose qui distingue une décision d'un accident.
    """
    if not reason or not reason.strip():
        raise ValueError("Une dérogation administrative doit être motivée.")

    entitlement = Entitlement.objects.create(
        user=user,
        organization=organization,
        source=Entitlement.Source.ADMIN_GRANT,
        access_right=access_right,
        scope_type=scope_type,
        scope_id=scope_id,
        starts_at=starts_at or timezone.now(),
        ends_at=ends_at,
        note=reason,
    )
    _audit(
        event_type="entitlement_granted",
        summary=f"Accès {access_right} accordé ({scope_type})",
        actor=actor,
        target=user or organization,
        metadata={
            "entitlement_id": entitlement.pk,
            "access_right": access_right,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "reason": reason,
        },
    )
    return entitlement
