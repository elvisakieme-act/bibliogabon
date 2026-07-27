from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from accounts.models import Entitlement, Organization, OrganizationMembership, User


def active_organization_ids_for_user(user: User, at=None) -> list[int]:
    at = at or timezone.now()
    memberships = OrganizationMembership.objects.filter(
        user=user,
        status=OrganizationMembership.Status.ACTIVE,
        starts_at__lte=at,
        organization__status=Organization.Status.ACTIVE,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))

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
