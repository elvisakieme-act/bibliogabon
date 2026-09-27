"""Signalement d'un document et demande de retrait.

Seule entrée publique de la tranche 4, et elle existe pour une raison simple :
un back-office qui traite des signalements que personne ne peut déposer est
une décoration.

Aucune limitation de débit ici, et c'est délibérément noté plutôt que corrigé à
moitié : le sujet appartient au durcissement de lancement, et une demi-mesure
laisserait croire le problème réglé.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import permissions as roles
from api.v1.errors import error_response
from catalog.models import Document
from operations.models import SupportTicket
from operations.services import report_document, request_document_withdrawal


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField()

    def validate_reason(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Un motif est obligatoire.")
        return value.strip()


def serialize_ticket(ticket: SupportTicket) -> dict:
    """La réponse porte le ticket, pas le document.

    Renvoyer le document ferait fuiter, à un simple signaleur, des métadonnées
    internes qu'il n'a pas à voir — et rappellerait au passage des chemins de
    stockage que rien ne doit exposer.
    """
    return {
        "id": ticket.pk,
        "category": ticket.category,
        "status": ticket.status,
        "title": ticket.title,
        "opened_at": ticket.opened_at,
    }


def _published_document(document_id: int) -> Document | None:
    """Un document non publié est *introuvable*, pas interdit.

    Répondre « interdit » confirmerait qu'un brouillon existe. C'est la règle
    du périmètre staff, et elle vaut ici pour la même raison.
    """
    return Document.objects.filter(
        pk=document_id, publication_status=Document.PublicationStatus.PUBLISHED
    ).first()


def _read_reason(request):
    serializer = ReasonSerializer(data=request.data)
    if not serializer.is_valid():
        return None, error_response(
            "invalid_request", "Motif manquant.", 400, serializer.errors
        )
    return serializer.validated_data["reason"], None


class DocumentReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Reports"],
        summary="Report a problem with a published document",
        description=(
            "Any authenticated reader may signal a problem. The report becomes "
            "a categorised ticket the back-office triages. A document that is "
            "not published returns 404: answering 403 would confirm a draft "
            "exists."
        ),
        operation_id="v1_document_report",
        request=ReasonSerializer,
    )
    def post(self, request, document_id: int):
        document = _published_document(document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        reason, refusal = _read_reason(request)
        if refusal is not None:
            return refusal

        ticket = report_document(document=document, reason=reason, reported_by=request.user)
        return Response(serialize_ticket(ticket), status=status.HTTP_201_CREATED)


class DocumentWithdrawalRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Reports"],
        summary="Request the withdrawal of a document",
        description=(
            "Reserved to the document's authors and to content admins. The "
            "request withdraws nothing: it opens a high-priority ticket that a "
            "moderator acts on, so contract-bound categories keep the "
            "protection `can_withdraw_document` gives them."
        ),
        operation_id="v1_document_withdrawal_request",
        request=ReasonSerializer,
    )
    def post(self, request, document_id: int):
        document = _published_document(document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        is_author = document.document_authors.filter(author__linked_user=request.user).exists()
        if not (is_author or roles.is_content_admin(request.user)):
            # Un lecteur gêné par un document le *signale* : c'est la voie
            # prévue pour lui, et elle n'engage pas un retrait.
            return error_response(
                "permission_denied",
                "Seul un auteur du document ou la modération peut en demander le retrait.",
                403,
            )

        reason, refusal = _read_reason(request)
        if refusal is not None:
            return refusal

        try:
            ticket = request_document_withdrawal(
                document=document, reason=reason, requested_by=request.user
            )
        except ValueError as exc:
            return error_response("request_refused", str(exc), 409)

        return Response(serialize_ticket(ticket), status=status.HTTP_201_CREATED)
