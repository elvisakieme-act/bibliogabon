"""Endpoints documents du back-office."""

from __future__ import annotations

from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response

from accounts import permissions as roles
from api.staff.v1.scoping import documents_visible_to
from api.staff.v1.serializers import (
    StaffDocumentWriteSerializer,
    serialize_staff_document,
)
from api.staff.v1.views import StaffAPIView
from api.v1.errors import error_response
from api.v1.pagination import StandardResultsSetPagination
from catalog.models import Author, Document, DocumentAuthor
from catalog.services import missing_deposit_requirements, missing_publication_requirements
from operations.services import record_audit_event


def get_visible_document(user, document_id: int) -> Document | None:
    """Un document hors portée est introuvable, pas interdit.

    Répondre 403 révélerait qu'il existe ; pour un brouillon d'autrui,
    cette seule information est déjà une fuite.
    """
    return documents_visible_to(user).filter(pk=document_id).first()


class StaffDocumentListView(StaffAPIView):
    @extend_schema(
        tags=["Staff documents"],
        summary="List documents visible to the caller",
        description=(
            "A content admin sees every publication state; a teacher sees only "
            "documents they authored. Never exposes storage keys."
        ),
        operation_id="staff_v1_documents_list",
        parameters=[
            OpenApiParameter("status", str, description="Publication status"),
            OpenApiParameter("domain", str, description="Academic domain slug"),
            OpenApiParameter("type", str, description="Document type slug"),
            OpenApiParameter("q", str, description="Title fragment"),
        ],
    )
    def get(self, request):
        queryset = documents_visible_to(request.user)

        if value := request.query_params.get("status"):
            queryset = queryset.filter(publication_status=value)
        if value := request.query_params.get("domain"):
            queryset = queryset.filter(academic_domain__slug=value)
        if value := request.query_params.get("type"):
            queryset = queryset.filter(document_type__slug=value)
        if value := request.query_params.get("q"):
            queryset = queryset.filter(title__icontains=value)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset.order_by("-updated_at", "id"), request, view=self)
        return paginator.get_paginated_response(
            [serialize_staff_document(document) for document in page]
        )

    @extend_schema(
        tags=["Staff documents"],
        summary="Create a document in draft",
        description=(
            "The document starts in draft. A teacher is attached as its first "
            "author, so they can find it again."
        ),
        operation_id="staff_v1_documents_create",
        request=StaffDocumentWriteSerializer,
    )
    def post(self, request):
        if not roles.can_submit_document(request.user):
            return error_response(
                "permission_denied", "Vous ne pouvez pas déposer de document.", 403
            )

        serializer = StaffDocumentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "invalid_request", "Le document est invalide.", 400, serializer.errors
            )

        with transaction.atomic():
            document = serializer.save(
                publication_status=Document.PublicationStatus.DRAFT
            )
            if roles.is_teacher_author(request.user):
                author, _ = Author.objects.get_or_create(
                    linked_user=request.user,
                    defaults={
                        "display_name": request.user.display_name or request.user.email,
                        "normalized_name": (
                            request.user.display_name or request.user.email
                        ).lower(),
                    },
                )
                DocumentAuthor.objects.create(
                    document=document, author=author, role=DocumentAuthor.Role.AUTHOR
                )
            record_audit_event(
                actor=request.user,
                event_type="document_created",
                target=document,
                summary=f"Document « {document.title} » créé",
                metadata={"document_id": document.pk},
            )

        document.refresh_from_db()
        return Response(serialize_staff_document(document), status=status.HTTP_201_CREATED)


class StaffDocumentDetailView(StaffAPIView):
    @extend_schema(
        tags=["Staff documents"],
        summary="Retrieve one document",
        operation_id="staff_v1_documents_retrieve",
    )
    def get(self, request, document_id: int):
        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)
        return Response(serialize_staff_document(document))

    @extend_schema(
        tags=["Staff documents"],
        summary="Update document metadata",
        description=(
            "Publication status is not writable here: it only advances through "
            "the audited transitions."
        ),
        operation_id="staff_v1_documents_update",
        request=StaffDocumentWriteSerializer,
    )
    def patch(self, request, document_id: int):
        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        serializer = StaffDocumentWriteSerializer(document, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(
                "invalid_request", "Le document est invalide.", 400, serializer.errors
            )
        serializer.save()
        document.refresh_from_db()
        return Response(serialize_staff_document(document))


class StaffDocumentSubmitView(StaffAPIView):
    @extend_schema(
        tags=["Staff documents"],
        summary="Submit a draft for review",
        description=(
            "draft → submitted. Refused, naming what is missing, when the "
            "document has no author or no valid rights agreement."
        ),
        operation_id="staff_v1_documents_submit",
        request=None,
    )
    def post(self, request, document_id: int):
        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        if document.publication_status == Document.PublicationStatus.SUBMITTED:
            return Response(serialize_staff_document(document))

        if document.publication_status != Document.PublicationStatus.DRAFT:
            return error_response(
                "invalid_transition",
                f"Un document en état « {document.publication_status} » ne peut pas être soumis.",
                409,
            )

        # Soumettre exige une *déclaration* complète, pas une déclaration
        # approuvée : l'approbation est l'acte du relecteur et vient après.
        missing = missing_deposit_requirements(document)
        if missing:
            return error_response(
                "incomplete_document",
                "Le document est incomplet et ne peut pas être soumis.",
                400,
                {"missing": missing},
            )

        with transaction.atomic():
            document.publication_status = Document.PublicationStatus.SUBMITTED
            document.save(update_fields=["publication_status", "updated_at"])
            record_audit_event(
                actor=request.user,
                event_type="document_submitted",
                target=document,
                summary=f"Document « {document.title} » soumis pour revue",
                metadata={"document_id": document.pk},
            )

        document.refresh_from_db()
        return Response(serialize_staff_document(document))
