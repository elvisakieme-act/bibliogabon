"""Organisations : membres, quotas et rapport d'usage.

Le risque produit de la tranche est ici. Tout passe par
`_get_organization`, qui interroge le prédicat **avec l'organisation en
argument** — jamais une liste filtrée après coup. Une organisation hors
périmètre est *introuvable* et non interdite : confirmer qu'elle existe
renseignerait déjà une institution sur une autre.

Aucune réponse ne nomme un lecteur. Ce n'est pas un report, c'est une
exclusion : un rapport qui dirait qui a lu quoi transformerait une
bibliothèque en outil de surveillance. Le rapport part donc de
`DailyUsageAggregate`, jamais de `PageAccessLog`.
"""

from __future__ import annotations

from datetime import date

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response

from accounts import permissions as roles
from accounts.models import Organization, OrganizationMembership, User
from accounts.services import (
    add_organization_member,
    end_organization_membership,
    suspend_organization_membership,
)
from analytics.services import generate_institution_report, serialize_institution_report
from api.staff.v1.views import StaffAPIView
from api.v1.errors import error_response
from api.v1.pagination import StandardResultsSetPagination
from billing.models import OrganizationQuota


def _get_organization(user, organization_id: int) -> Organization | None:
    """Le prédicat reçoit l'organisation ; il ne filtre pas une liste.

    Un filtre appliqué après coup exposerait les membres d'une institution à
    une autre dès qu'il divergerait du prédicat — et le cas nominal
    continuerait de marcher parfaitement, ce qui rend le défaut invisible.
    """
    organization = Organization.objects.filter(pk=organization_id).first()
    if organization is None:
        return None
    if not roles.administers_organization(user, organization):
        return None
    return organization


def serialize_organization(organization: Organization) -> dict:
    return {
        "id": organization.pk,
        "name": organization.name,
        "slug": organization.slug,
        "organization_type": organization.organization_type,
        "status": organization.status,
        "requires_identity_verification": organization.requires_identity_verification,
    }


def serialize_membership(membership: OrganizationMembership) -> dict:
    return {
        "id": membership.pk,
        "user": {
            "id": membership.user_id,
            "email": membership.user.email,
            "display_name": membership.user.display_name or membership.user.email,
        },
        "role": membership.role,
        "status": membership.status,
        # Une adhésion non vérifiée n'accorde rien. Sans ce champ à l'écran,
        # un administrateur ne comprendra pas pourquoi un membre ne peut pas
        # lire, et conclura que la plateforme est cassée.
        "verification_status": membership.verification_status,
        "verification_method": membership.verification_method,
        "starts_at": membership.starts_at,
        "ends_at": membership.ends_at,
    }


def serialize_quota(quota: OrganizationQuota) -> dict:
    return {
        "id": quota.pk,
        "status": quota.status,
        "seat_limit": quota.seat_limit,
        "offer": {"id": quota.offer_id, "name": quota.offer.name},
        "contract_reference": quota.contract_reference,
        "starts_at": quota.starts_at,
        "ends_at": quota.ends_at,
    }


class OrganizationListView(StaffAPIView):
    @extend_schema(
        tags=["Staff organizations"],
        summary="List the organizations the caller administers",
        description="Platform staff see all; anyone else sees only their own.",
        operation_id="staff_v1_organizations_list",
    )
    def get(self, request):
        if roles.is_platform_staff(request.user):
            queryset = Organization.objects.all()
        else:
            queryset = Organization.objects.filter(
                pk__in=roles.administered_organization_ids(request.user)
            )

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset.order_by("name", "id"), request, view=self)
        return paginator.get_paginated_response([serialize_organization(o) for o in page])


class OrganizationDetailView(StaffAPIView):
    @extend_schema(
        tags=["Staff organizations"],
        summary="Retrieve one organization",
        operation_id="staff_v1_organizations_retrieve",
    )
    def get(self, request, organization_id: int):
        organization = _get_organization(request.user, organization_id)
        if organization is None:
            return error_response("not_found", "Organisation introuvable.", 404)
        payload = serialize_organization(organization)
        payload["active_member_count"] = OrganizationMembership.objects.filter(
            organization=organization, status=OrganizationMembership.Status.ACTIVE
        ).count()
        return Response(payload)


class MemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=OrganizationMembership.Role.choices,
        default=OrganizationMembership.Role.MEMBER,
    )


class OrganizationMemberListView(StaffAPIView):
    @extend_schema(
        tags=["Staff organizations"],
        summary="List the members of one organization",
        operation_id="staff_v1_organization_members_list",
    )
    def get(self, request, organization_id: int):
        organization = _get_organization(request.user, organization_id)
        if organization is None:
            return error_response("not_found", "Organisation introuvable.", 404)

        queryset = OrganizationMembership.objects.filter(
            organization=organization
        ).select_related("user")
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(
            queryset.order_by("user__email", "id"), request, view=self
        )
        return paginator.get_paginated_response([serialize_membership(m) for m in page])

    @extend_schema(
        tags=["Staff organizations"],
        summary="Attach an existing account to the organization",
        description=(
            "The account must already exist: creating one here would make an "
            "organization able to mint identities, which belongs to signup."
        ),
        operation_id="staff_v1_organization_members_add",
        request=MemberSerializer,
    )
    def post(self, request, organization_id: int):
        organization = _get_organization(request.user, organization_id)
        if organization is None:
            return error_response("not_found", "Organisation introuvable.", 404)
        if not roles.can_manage_organization_members(request.user, organization):
            return error_response("permission_denied", "Gestion des membres refusée.", 403)

        serializer = MemberSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "invalid_request", "Requête invalide.", 400, serializer.errors
            )

        user = User.objects.filter(email=serializer.validated_data["email"]).first()
        if user is None:
            return error_response(
                "invalid_request",
                "Aucun compte ne correspond à cette adresse.",
                400,
                {"email": ["Cette personne doit d'abord créer un compte."]},
            )

        membership = add_organization_member(
            organization=organization,
            user=user,
            role=serializer.validated_data["role"],
            actor=request.user,
        )
        return Response(serialize_membership(membership), status=status.HTTP_201_CREATED)


class ReasonSerializer(serializers.Serializer):
    """Le motif est obligatoire, comme pour le retrait et l'archivage.

    Il l'était d'abord facultatif, par mimétisme avec la signature du service,
    qui lui donne une valeur par défaut. Mais une suspension sans raison
    enregistrée est le même défaut qu'un retrait sans motif : un acte dont
    personne ne peut rendre compte, alors que c'est précisément ce que l'audit
    doit permettre.
    """

    reason = serializers.CharField()

    def validate_reason(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError(
                "Un motif est obligatoire : il est conservé au journal d'audit."
            )
        return value.strip()


def _get_membership(user, organization_id: int, membership_id: int):
    organization = _get_organization(user, organization_id)
    if organization is None:
        return None, None
    membership = OrganizationMembership.objects.filter(
        pk=membership_id, organization=organization
    ).first()
    return organization, membership


class OrganizationMemberSuspendView(StaffAPIView):
    @extend_schema(
        tags=["Staff organizations"],
        summary="Suspend a membership",
        description=(
            "Reading access granted by the organization stops immediately, "
            "because it depends on an active membership. The account itself is "
            "untouched."
        ),
        operation_id="staff_v1_organization_member_suspend",
        request=ReasonSerializer,
    )
    def post(self, request, organization_id: int, membership_id: int):
        organization, membership = _get_membership(request.user, organization_id, membership_id)
        if organization is None or membership is None:
            return error_response("not_found", "Adhésion introuvable.", 404)
        if not roles.can_manage_organization_members(request.user, organization):
            return error_response("permission_denied", "Gestion des membres refusée.", 403)

        serializer = ReasonSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("invalid_request", "Motif manquant.", 400, serializer.errors)
        suspend_organization_membership(
            membership=membership,
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
        membership.refresh_from_db()
        return Response(serialize_membership(membership))


class OrganizationMemberEndView(StaffAPIView):
    @extend_schema(
        tags=["Staff organizations"],
        summary="End a membership",
        description=(
            "Ends the access the organization granted. It deletes neither the "
            "account, nor its history, nor its other entitlements."
        ),
        operation_id="staff_v1_organization_member_end",
        request=ReasonSerializer,
    )
    def post(self, request, organization_id: int, membership_id: int):
        organization, membership = _get_membership(request.user, organization_id, membership_id)
        if organization is None or membership is None:
            return error_response("not_found", "Adhésion introuvable.", 404)
        if not roles.can_manage_organization_members(request.user, organization):
            return error_response("permission_denied", "Gestion des membres refusée.", 403)

        serializer = ReasonSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("invalid_request", "Motif manquant.", 400, serializer.errors)
        end_organization_membership(
            membership=membership,
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
        membership.refresh_from_db()
        return Response(serialize_membership(membership))


class OrganizationQuotaListView(StaffAPIView):
    @extend_schema(
        tags=["Staff organizations"],
        summary="List the quotas and contracts of one organization",
        operation_id="staff_v1_organization_quotas_list",
    )
    def get(self, request, organization_id: int):
        organization = _get_organization(request.user, organization_id)
        if organization is None:
            return error_response("not_found", "Organisation introuvable.", 404)

        queryset = OrganizationQuota.objects.filter(organization=organization).select_related(
            "offer"
        )
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(
            queryset.order_by("-starts_at", "id"), request, view=self
        )
        return paginator.get_paginated_response([serialize_quota(q) for q in page])


class OrganizationReportView(StaffAPIView):
    @extend_schema(
        tags=["Staff organizations"],
        summary="Usage report for one organization over a period",
        description=(
            "Aggregated metrics only. No payload at any level names who read "
            "what: the report is built from DailyUsageAggregate, never from "
            "PageAccessLog."
        ),
        operation_id="staff_v1_organization_report",
        parameters=[
            OpenApiParameter(
                "from", str, description="ISO date, default the first of this month"
            ),
            OpenApiParameter("to", str, description="ISO date, default today"),
        ],
    )
    def get(self, request, organization_id: int):
        organization = _get_organization(request.user, organization_id)
        if organization is None:
            return error_response("not_found", "Organisation introuvable.", 404)
        if not roles.can_view_organization_reports(request.user, organization):
            return error_response("permission_denied", "Rapport refusé.", 403)

        today = date.today()
        try:
            period_start = (
                date.fromisoformat(request.query_params["from"])
                if "from" in request.query_params
                else today.replace(day=1)
            )
            period_end = (
                date.fromisoformat(request.query_params["to"])
                if "to" in request.query_params
                else today
            )
        except ValueError:
            return error_response(
                "invalid_request",
                "Période invalide.",
                400,
                {"from": ["Une date ISO est attendue, par exemple 2026-09-01."]},
            )

        if period_start > period_end:
            return error_response(
                "invalid_request",
                "Période invalide.",
                400,
                {"to": ["La fin de période précède son début."]},
            )

        report = generate_institution_report(
            organization, period_start, period_end, generated_by=request.user
        )
        return Response(serialize_institution_report(report))
