"""Auteurs et déclaration de droits.

Le point le plus sensible du produit se joue ici. Si un déposant peut
porter lui-même `authorization_status` à `approved`, il s'auto-certifie,
et le risque « droits d'auteur mal clarifiés » — classé critique dans le
plan directeur — se réalise par une simple requête HTTP.

La séparation des pouvoirs est donc structurelle, pas conventionnelle :
le sérialiseur de déclaration n'expose tout simplement pas les champs de
décision, et l'endpoint de décision est fermé aux non-modérateurs.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response

from accounts import permissions as roles
from api.staff.v1.documents import get_visible_document
from api.staff.v1.serializers import serialize_staff_document
from api.staff.v1.views import StaffAPIView
from api.v1.errors import error_response
from catalog.models import DocumentAuthor, RightsAgreement
from operations.services import record_audit_event


class DocumentAuthorWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentAuthor
        fields = ["author", "role"]
        # `position` est calculée : la laisser au client ouvrirait des trous
        # et des collisions sur la contrainte d'unicité.


class RightsDeclarationSerializer(serializers.ModelSerializer):
    """Ce qu'un déposant a le droit de déclarer.

    `authorization_status`, `authorization_date`, `reviewer_decision`,
    `rejection_reason` et `audit_reference` sont absents à dessein : ils
    appartiennent au relecteur. Un client qui les enverrait les verrait
    simplement ignorés.
    """

    class Meta:
        model = RightsAgreement
        fields = [
            "agreement_type",
            "rights_holder_name",
            "access_model",
            "withdrawal_rule",
            "revenue_sharing_rule",
            "confidentiality_terms",
            "consent_reference",
            "valid_from",
            "valid_until",
        ]


class RightsDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approved", "rejected"])
    reviewer_decision = serializers.CharField()
    audit_reference = serializers.CharField(required=False, allow_blank=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        errors = {}
        if attrs["decision"] == "approved" and not attrs.get("audit_reference", "").strip():
            # La référence d'audit est le lien vers le contrat signé hors
            # ligne : sans elle, l'approbation n'est pas traçable.
            errors["audit_reference"] = [
                "Une approbation doit référencer le contrat ou l'autorisation signée."
            ]
        if attrs["decision"] == "rejected" and not attrs.get("rejection_reason", "").strip():
            errors["rejection_reason"] = [
                "Un rejet doit être motivé, pour l'audit interne."
            ]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class DocumentAuthorListView(StaffAPIView):
    @extend_schema(
        tags=["Staff documents"],
        summary="Attach an author to a document",
        operation_id="staff_v1_document_authors_attach",
        request=DocumentAuthorWriteSerializer,
    )
    def post(self, request, document_id: int):
        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        serializer = DocumentAuthorWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "invalid_request", "Auteur invalide.", 400, serializer.errors
            )

        next_position = (
            DocumentAuthor.objects.filter(document=document).aggregate(Max("position"))[
                "position__max"
            ]
            or 0
        ) + 1
        try:
            with transaction.atomic():
                serializer.save(document=document, position=next_position)
        except IntegrityError:
            return error_response(
                "author_already_attached",
                "Cet auteur est déjà rattaché au document.",
                409,
            )

        document.refresh_from_db()
        return Response(serialize_staff_document(document), status=status.HTTP_201_CREATED)


class DocumentAuthorDetailView(StaffAPIView):
    @extend_schema(
        tags=["Staff documents"],
        summary="Detach an author from a document",
        operation_id="staff_v1_document_authors_detach",
    )
    def delete(self, request, document_id: int, author_id: int):
        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        entry = DocumentAuthor.objects.filter(document=document, author_id=author_id).first()
        if entry is None:
            return error_response("not_found", "Auteur non rattaché.", 404)

        with transaction.atomic():
            entry.delete()
            # Les positions restent contiguës : un trou ferait dériver le
            # rang affiché et la contrainte d'unicité à la prochaine insertion.
            for rank, remaining in enumerate(
                DocumentAuthor.objects.filter(document=document).order_by("position", "id"),
                start=1,
            ):
                if remaining.position != rank:
                    remaining.position = rank
                    remaining.save(update_fields=["position"])

        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentRightsView(StaffAPIView):
    @extend_schema(
        tags=["Staff rights"],
        summary="Declare or replace the rights agreement",
        description=(
            "The depositor declares. Authorisation status, date, reviewer "
            "decision and audit reference are not writable here — they belong "
            "to the reviewer."
        ),
        operation_id="staff_v1_document_rights_declare",
        request=RightsDeclarationSerializer,
    )
    def put(self, request, document_id: int):
        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        existing = RightsAgreement.objects.filter(document=document).first()
        if existing and existing.authorization_status == (
            RightsAgreement.AuthorizationStatus.APPROVED
        ) and not roles.can_review_publication(request.user):
            return error_response(
                "rights_already_approved",
                "Cette déclaration a été approuvée et ne peut plus être modifiée "
                "sans passer par un modérateur.",
                409,
            )

        serializer = RightsDeclarationSerializer(existing, data=request.data)
        if not serializer.is_valid():
            return error_response(
                "invalid_request", "Déclaration de droits invalide.", 400, serializer.errors
            )

        with transaction.atomic():
            agreement = serializer.save(
                document=document,
                # Toute déclaration repart en attente de revue : modifier une
                # déclaration après coup doit relancer la vérification.
                authorization_status=RightsAgreement.AuthorizationStatus.PENDING_REVIEW,
                authorization_date=None,
                reviewer_decision="",
                rejection_reason="",
                audit_reference="",
            )
            record_audit_event(
                actor=request.user,
                event_type="rights_agreement_declared",
                target=document,
                summary=f"Droits déclarés pour « {document.title} »",
                metadata={
                    "document_id": document.pk,
                    "agreement_type": agreement.agreement_type,
                    "rights_holder_name": agreement.rights_holder_name,
                },
            )

        document.refresh_from_db()
        return Response(serialize_staff_document(document))


class DocumentRightsDecisionView(StaffAPIView):
    @extend_schema(
        tags=["Staff rights"],
        summary="Approve or reject a rights declaration",
        description=(
            "Reserved to content admins. An approval must carry the audit "
            "reference of the signed contract; a rejection must carry a reason."
        ),
        operation_id="staff_v1_document_rights_decide",
        request=RightsDecisionSerializer,
    )
    def post(self, request, document_id: int):
        if not roles.can_review_publication(request.user):
            return error_response(
                "permission_denied",
                "Seul un modérateur de contenu peut se prononcer sur les droits.",
                403,
            )

        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        agreement = RightsAgreement.objects.filter(document=document).first()
        if agreement is None:
            return error_response(
                "rights_agreement_missing",
                "Aucune déclaration de droits à examiner.",
                409,
            )

        serializer = RightsDecisionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "invalid_request", "Décision invalide.", 400, serializer.errors
            )
        decision = serializer.validated_data

        approved = decision["decision"] == "approved"
        with transaction.atomic():
            agreement.authorization_status = (
                RightsAgreement.AuthorizationStatus.APPROVED
                if approved
                else RightsAgreement.AuthorizationStatus.REJECTED
            )
            # Horodatée par le système : une date fournie par le client
            # pourrait antidater une autorisation.
            agreement.authorization_date = timezone.now().date() if approved else None
            agreement.reviewer_decision = decision["reviewer_decision"]
            agreement.audit_reference = decision.get("audit_reference", "")
            agreement.rejection_reason = decision.get("rejection_reason", "")
            agreement.save()

            record_audit_event(
                actor=request.user,
                event_type=(
                    "rights_agreement_approved" if approved else "rights_agreement_rejected"
                ),
                target=document,
                summary=(
                    f"Droits {'approuvés' if approved else 'rejetés'} pour "
                    f"« {document.title} »"
                ),
                metadata={
                    "document_id": document.pk,
                    "reviewer_decision": decision["reviewer_decision"],
                    "audit_reference": decision.get("audit_reference", ""),
                    "rejection_reason": decision.get("rejection_reason", ""),
                },
            )

        document.refresh_from_db()
        return Response(serialize_staff_document(document))
