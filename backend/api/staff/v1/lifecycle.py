"""Fin de vie d'un document, et sa trace.

Retrait, archivage et journal d'audit. Les trois vont ensemble : les deux
premiers sont des actes dont on doit pouvoir rendre compte, le troisième est
ce qui permet d'en rendre compte.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response

from accounts import permissions as roles
from api.staff.v1.documents import get_visible_document
from api.staff.v1.serializers import serialize_staff_document
from api.staff.v1.views import StaffAPIView
from api.v1.errors import error_response
from api.v1.pagination import StandardResultsSetPagination
from operations.models import AuditLog
from operations.services import archive_document, withdraw_document

# Champs de `metadata` qu'un journal peut montrer.
#
# `metadata` est écrit par de nombreux services, et rien n'empêche l'un d'eux
# d'y placer un jour une clé de stockage — l'ingestion en manipule à longueur
# de temps. Une liste blanche vaut mieux qu'une liste noire : une règle de
# confidentialité qui dépend de la prudence de chaque auteur futur n'est pas
# une règle. Un test la sollicite avec un événement délibérément empoisonné.
AUDIT_METADATA_ALLOW_LIST = frozenset(
    {
        "reason",
        "document_id",
        "review_id",
        "reviewer_id",
        "decision_reason",
        "audit_reference",
        "rejection_reason",
        "version_label",
        "byte_size",
        "page_count",
        "organization_id",
    }
)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField()

    def validate_reason(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError(
                "Un motif est obligatoire : un document qui disparaît sans raison "
                "enregistrée est exactement ce qu'un audit sert à empêcher."
            )
        return value.strip()


def _read_reason(request):
    serializer = ReasonSerializer(data=request.data)
    if not serializer.is_valid():
        return None, error_response(
            "invalid_request", "Motif manquant.", 400, serializer.errors
        )
    return serializer.validated_data["reason"], None


class DocumentWithdrawView(StaffAPIView):
    @extend_schema(
        tags=["Staff lifecycle"],
        summary="Withdraw a published document",
        description=(
            "Reversible internally: pages, version, index and rights stay. Only "
            "readability changes. A teacher may withdraw their own voluntary "
            "deposit, but not a contract-bound category, where a unilateral "
            "withdrawal would breach an agreement."
        ),
        operation_id="staff_v1_document_withdraw",
        request=ReasonSerializer,
    )
    def post(self, request, document_id: int):
        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)
        if not roles.can_withdraw_document(request.user, document):
            return error_response(
                "permission_denied",
                "Vous ne pouvez pas retirer ce document.",
                403,
            )

        reason, refusal = _read_reason(request)
        if refusal is not None:
            return refusal

        try:
            withdraw_document(document=document, reason=reason, actor=request.user)
        except ValueError as exc:
            return error_response("withdrawal_refused", str(exc), 409)

        document.refresh_from_db()
        return Response(serialize_staff_document(document))


class DocumentArchiveView(StaffAPIView):
    @extend_schema(
        tags=["Staff lifecycle"],
        summary="Archive a document",
        description=(
            "End of the document's life on the platform, and not a reversible "
            "withdrawal — hence content admins only, whatever the category."
        ),
        operation_id="staff_v1_document_archive",
        request=ReasonSerializer,
    )
    def post(self, request, document_id: int):
        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)
        if not roles.is_content_admin(request.user):
            return error_response(
                "permission_denied",
                "Seul un modérateur de contenu archive un document.",
                403,
            )

        reason, refusal = _read_reason(request)
        if refusal is not None:
            return refusal

        try:
            archive_document(document=document, reason=reason, actor=request.user)
        except ValueError as exc:
            return error_response("archive_refused", str(exc), 409)

        document.refresh_from_db()
        return Response(serialize_staff_document(document))


class DocumentAuditView(StaffAPIView):
    @extend_schema(
        tags=["Staff lifecycle"],
        summary="Read the audit trail of one document",
        description=(
            "Who did what, when and why. Metadata passes through an allow-list: "
            "it is written by many services and one of them could put a storage "
            "key in it."
        ),
        operation_id="staff_v1_document_audit",
    )
    def get(self, request, document_id: int):
        if not roles.can_review_publication(request.user):
            # Le journal nomme qui a fait quoi sur l'ensemble du catalogue.
            return error_response(
                "permission_denied",
                "Seul un modérateur de contenu consulte le journal.",
                403,
            )
        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        events = AuditLog.objects.filter(
            target_app="catalog",
            target_model="document",
            target_id=str(document.pk),
        ).select_related("actor")

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(events, request, view=self)
        return paginator.get_paginated_response([serialize_audit_event(e) for e in page])


def serialize_audit_event(event: AuditLog) -> dict:
    return {
        "id": event.pk,
        "event_type": event.event_type,
        "summary": event.summary,
        "created_at": event.created_at,
        "actor": (
            None
            if event.actor is None
            else {
                "id": event.actor.pk,
                "display_name": event.actor.display_name or event.actor.email,
            }
        ),
        "metadata": {
            key: value
            for key, value in (event.metadata or {}).items()
            if key in AUDIT_METADATA_ALLOW_LIST
        },
    }
