"""File de support, signalements et demandes de retrait.

Le cadrage est le point sensible : un administrateur d'organisation ne voit que
les tickets de la sienne. Il est obtenu en **filtrant sur les organisations
qu'il administre**, liste que `administered_organization_ids` calcule à partir
d'adhésions actives et vérifiées — la même source que le contrôle de lecture.
Un filtre bricolé ici divergerait de ce contrôle sans que rien ne le signale.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response

from accounts import permissions as roles
from api.staff.v1.views import StaffAPIView
from api.v1.errors import error_response
from api.v1.pagination import StandardResultsSetPagination
from operations.models import SupportTicket
from operations.services import resolve_support_ticket


class ResolutionSerializer(serializers.Serializer):
    resolution_summary = serializers.CharField()

    def validate_resolution_summary(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError(
                "Un résumé de résolution est obligatoire : il est conservé au journal."
            )
        return value.strip()


def _person(user) -> dict | None:
    if user is None:
        return None
    return {"id": user.pk, "display_name": user.display_name or user.email}


def serialize_ticket(ticket: SupportTicket) -> dict:
    """Le ticket, et du document juste de quoi le retrouver.

    Sérialiser le document entier ferait entrer, dans une file de support, des
    métadonnées que son cadrage ne couvre pas — un administrateur
    d'organisation n'a pas à lire l'état de publication d'un brouillon parce
    qu'un ticket le mentionne.
    """
    return {
        "id": ticket.pk,
        "category": ticket.category,
        "status": ticket.status,
        "priority": ticket.priority,
        "title": ticket.title,
        "description": ticket.description,
        "created_by": _person(ticket.created_by),
        "assigned_to": _person(ticket.assigned_to),
        "document": (
            None
            if ticket.document_id is None
            else {
                "id": ticket.document_id,
                "title": ticket.document.title,
                "slug": ticket.document.slug,
            }
        ),
        "organization": (
            None
            if ticket.organization_id is None
            else {"id": ticket.organization_id, "name": ticket.organization.name}
        ),
        "resolution_summary": ticket.resolution_summary,
        "opened_at": ticket.opened_at,
        "resolved_at": ticket.resolved_at,
    }


def tickets_visible_to(user):
    """Le périmètre d'un utilisateur sur la file.

    Un modérateur ou le staff plateforme voient tout ; un administrateur
    d'organisation ne voit que les tickets rattachés aux siennes. Un ticket
    sans organisation — une question de facturation d'un particulier — ne le
    concerne donc pas.
    """
    queryset = SupportTicket.objects.select_related("document", "organization").all()
    if roles.is_content_admin(user) or roles.is_platform_staff(user):
        return queryset
    organization_ids = roles.administered_organization_ids(user)
    if not organization_ids:
        return SupportTicket.objects.none()
    return queryset.filter(organization_id__in=organization_ids)


def _may_see_queue(user) -> bool:
    return (
        roles.is_content_admin(user)
        or roles.is_platform_staff(user)
        or bool(roles.administered_organization_ids(user))
    )


class TicketListView(StaffAPIView):
    @extend_schema(
        tags=["Staff support"],
        summary="List support tickets, document reports and withdrawal requests",
        description=(
            "Content admins and platform staff see everything; an organization "
            "admin sees only tickets attached to their own organizations."
        ),
        operation_id="staff_v1_tickets_list",
        parameters=[
            OpenApiParameter(
                "category", str, description="support | document_report | withdrawal_request"
            ),
            OpenApiParameter("status", str, description="Ticket status"),
        ],
    )
    def get(self, request):
        if not _may_see_queue(request.user):
            return error_response(
                "permission_denied", "Vous n'avez pas accès à la file de support.", 403
            )

        queryset = tickets_visible_to(request.user)
        if value := request.query_params.get("category"):
            queryset = queryset.filter(category=value)
        if value := request.query_params.get("status"):
            queryset = queryset.filter(status=value)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(
            queryset.order_by("-priority", "opened_at", "id"), request, view=self
        )
        return paginator.get_paginated_response([serialize_ticket(t) for t in page])


def _get_ticket(user, ticket_id: int) -> SupportTicket | None:
    """Hors périmètre, un ticket est *introuvable*, pas interdit : confirmer
    qu'il existe est déjà une fuite vers une autre institution."""
    if not _may_see_queue(user):
        return None
    return tickets_visible_to(user).filter(pk=ticket_id).first()


class TicketDetailView(StaffAPIView):
    @extend_schema(
        tags=["Staff support"],
        summary="Retrieve one ticket",
        operation_id="staff_v1_tickets_retrieve",
    )
    def get(self, request, ticket_id: int):
        ticket = _get_ticket(request.user, ticket_id)
        if ticket is None:
            return error_response("not_found", "Ticket introuvable.", 404)
        return Response(serialize_ticket(ticket))


class TicketAssignView(StaffAPIView):
    @extend_schema(
        tags=["Staff support"],
        summary="Take a ticket",
        operation_id="staff_v1_tickets_assign",
        request=None,
    )
    def post(self, request, ticket_id: int):
        ticket = _get_ticket(request.user, ticket_id)
        if ticket is None:
            return error_response("not_found", "Ticket introuvable.", 404)
        if ticket.status in {SupportTicket.Status.RESOLVED, SupportTicket.Status.CANCELLED}:
            return error_response("ticket_closed", "Ce ticket est déjà clos.", 409)

        ticket.assigned_to = request.user
        ticket.status = SupportTicket.Status.IN_PROGRESS
        ticket.save(update_fields=["assigned_to", "status", "updated_at"])
        return Response(serialize_ticket(ticket))


class TicketResolveView(StaffAPIView):
    @extend_schema(
        tags=["Staff support"],
        summary="Resolve a ticket",
        description=(
            "Resolution is an answer, not an act. Closing a withdrawal-request "
            "ticket withdraws nothing: the moderator must act on the document."
        ),
        operation_id="staff_v1_tickets_resolve",
        request=ResolutionSerializer,
    )
    def post(self, request, ticket_id: int):
        ticket = _get_ticket(request.user, ticket_id)
        if ticket is None:
            return error_response("not_found", "Ticket introuvable.", 404)

        serializer = ResolutionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "invalid_request", "Résolution invalide.", 400, serializer.errors
            )

        try:
            resolve_support_ticket(
                ticket=ticket,
                actor=request.user,
                resolution_summary=serializer.validated_data["resolution_summary"],
            )
        except ValueError as exc:
            return error_response("resolution_refused", str(exc), 409)

        ticket.refresh_from_db()
        return Response(serialize_ticket(ticket))
