"""File de revue de publication.

Le domaine — `PublicationReview`, `record_publication_decision` — existait déjà
et était testé ; rien ne l'atteignait depuis l'extérieur d'un shell Python. Ce
module ajoute la surface, et rien d'autre.

Une différence avec le reste du back-office mérite d'être signalée : la file
est la **seule** liste qui n'est pas cadrée par la paternité. Un relecteur doit
voir ce que d'autres ont déposé, sans quoi il n'y a pas de relecture. Elle est
donc cadrée par le rôle — `can_review_publication`, réservé à
l'administration de contenu.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response

from accounts import permissions as roles
from api.staff.v1.serializers import serialize_staff_document
from api.staff.v1.views import StaffAPIView
from api.v1.errors import error_response
from api.v1.pagination import StandardResultsSetPagination
from catalog.models import Document
from catalog.services import missing_publication_requirements
from operations.models import PublicationReview
from operations.services import open_publication_review, record_publication_decision


class ReviewDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approved", "rejected", "cancelled"])
    reason = serializers.CharField(allow_blank=True, required=False, default="")

    def validate(self, attrs):
        # Le modèle refuse déjà un rejet sans motif ; le dire ici place
        # l'erreur sur le champ, là où le formulaire l'attend.
        if attrs["decision"] == "rejected" and not attrs.get("reason", "").strip():
            raise serializers.ValidationError(
                {"reason": ["Un rejet doit être motivé, pour l'audit interne."]}
            )
        return attrs


class ReviewOpenSerializer(serializers.Serializer):
    document = serializers.PrimaryKeyRelatedField(queryset=Document.objects.all())
    internal_notes = serializers.CharField(allow_blank=True, required=False, default="")


def serialize_review(review: PublicationReview) -> dict:
    return {
        "id": review.pk,
        "status": review.status,
        "document": serialize_staff_document(review.document),
        "opened_by": _person(review.opened_by),
        "reviewer": _person(review.reviewer),
        "decided_by": _person(review.decided_by),
        "decision_reason": review.decision_reason,
        "internal_notes": review.internal_notes,
        "opened_at": review.opened_at,
        "decided_at": review.decided_at,
    }


def _person(user) -> dict | None:
    """Identité minimale d'un intervenant : de quoi nommer qui a décidé, sans
    livrer un profil au passage."""
    if user is None:
        return None
    return {
        "id": user.pk,
        "display_name": user.display_name or user.email,
    }


def _authored_by(user, document: Document) -> bool:
    return document.document_authors.filter(author__linked_user=user).exists()


class ReviewListView(StaffAPIView):
    @extend_schema(
        tags=["Staff reviews"],
        summary="List publication reviews",
        description=(
            "Reserved to content admins. Unlike every other staff listing, this "
            "one is not scoped by authorship: a reviewer must see what others "
            "deposited. Each row carries what the document still misses for "
            "publication, so the queue is legible before opening a file."
        ),
        operation_id="staff_v1_reviews_list",
        parameters=[
            OpenApiParameter("status", str, description="Review status, default open"),
            OpenApiParameter("assigned", str, description="me | none | any"),
        ],
    )
    def get(self, request):
        if not roles.can_review_publication(request.user):
            return error_response(
                "permission_denied", "Seul un modérateur de contenu accède à la file.", 403
            )

        queryset = PublicationReview.objects.select_related("document").all()
        queryset = queryset.filter(
            status=request.query_params.get("status") or PublicationReview.Status.OPEN
        )
        assigned = request.query_params.get("assigned")
        if assigned == "me":
            queryset = queryset.filter(reviewer=request.user)
        elif assigned == "none":
            queryset = queryset.filter(reviewer__isnull=True)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(
            queryset.order_by("opened_at", "id"), request, view=self
        )
        return paginator.get_paginated_response([serialize_review(review) for review in page])

    @extend_schema(
        tags=["Staff reviews"],
        summary="Open a review on a submitted document",
        description=(
            "Idempotent: a document already under review returns its open "
            "review rather than a second one."
        ),
        operation_id="staff_v1_reviews_open",
        request=ReviewOpenSerializer,
    )
    def post(self, request):
        if not roles.can_review_publication(request.user):
            return error_response(
                "permission_denied", "Seul un modérateur de contenu ouvre une revue.", 403
            )

        serializer = ReviewOpenSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "invalid_request", "Requête invalide.", 400, serializer.errors
            )

        document = serializer.validated_data["document"]
        if document.publication_status != Document.PublicationStatus.SUBMITTED:
            # Relire un brouillon reviendrait à juger un dossier que son auteur
            # n'a pas fini de constituer.
            return error_response(
                "document_not_submitted",
                "Seul un document soumis peut entrer en revue.",
                409,
                {"document": [f"État actuel : {document.publication_status}."]},
            )

        review = open_publication_review(
            document=document,
            actor=request.user,
            internal_notes=serializer.validated_data["internal_notes"],
        )
        return Response(serialize_review(review), status=status.HTTP_201_CREATED)


def _get_review(review_id: int) -> PublicationReview | None:
    return PublicationReview.objects.select_related("document").filter(pk=review_id).first()


class ReviewDetailView(StaffAPIView):
    @extend_schema(
        tags=["Staff reviews"],
        summary="Retrieve one review with its document",
        operation_id="staff_v1_reviews_retrieve",
    )
    def get(self, request, review_id: int):
        if not roles.can_review_publication(request.user):
            return error_response("permission_denied", "Accès refusé.", 403)
        review = _get_review(review_id)
        if review is None:
            return error_response("not_found", "Revue introuvable.", 404)
        return Response(serialize_review(review))


class ReviewAssignView(StaffAPIView):
    @extend_schema(
        tags=["Staff reviews"],
        summary="Take a review",
        description="Assigns the caller as reviewer. No automatic balancing.",
        operation_id="staff_v1_reviews_assign",
        request=None,
    )
    def post(self, request, review_id: int):
        if not roles.can_review_publication(request.user):
            return error_response("permission_denied", "Accès refusé.", 403)
        review = _get_review(review_id)
        if review is None:
            return error_response("not_found", "Revue introuvable.", 404)
        if review.status != PublicationReview.Status.OPEN:
            return error_response("review_closed", "Cette revue est déjà close.", 409)

        review.reviewer = request.user
        review.save(update_fields=["reviewer", "updated_at"])
        return Response(serialize_review(review))


class ReviewDecisionView(StaffAPIView):
    @extend_schema(
        tags=["Staff reviews"],
        summary="Decide on a review",
        description=(
            "Approve, reject or cancel. A rejection requires a reason. A content "
            "admin who authored the document is refused: the separation of "
            "duties must not depend on role assignment alone."
        ),
        operation_id="staff_v1_reviews_decide",
        request=ReviewDecisionSerializer,
    )
    def post(self, request, review_id: int):
        if not roles.can_review_publication(request.user):
            return error_response(
                "permission_denied", "Seul un modérateur de contenu décide.", 403
            )

        review = _get_review(review_id)
        if review is None:
            return error_response("not_found", "Revue introuvable.", 404)

        if _authored_by(request.user, review.document):
            # Sans ce refus, la séparation des pouvoirs ne tiendrait qu'à la
            # façon dont les rôles ont été attribués.
            return error_response(
                "self_review_forbidden",
                "Vous ne pouvez pas décider sur un document dont vous êtes auteur.",
                403,
            )

        serializer = ReviewDecisionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "invalid_request", "Décision invalide.", 400, serializer.errors
            )
        decision = serializer.validated_data

        if review.status != PublicationReview.Status.OPEN:
            return error_response("review_closed", "Cette revue est déjà close.", 409)

        if decision["decision"] == PublicationReview.Status.APPROVED:
            missing = missing_publication_requirements(review.document)
            if missing:
                # Le relecteur doit savoir ce qui bloque, pas seulement que ça
                # bloque : une porte fermée sans raison se lit comme une panne.
                return error_response(
                    "document_not_publishable",
                    "Ce document ne remplit pas encore les conditions de publication.",
                    409,
                    {"missing_for_publication": missing},
                )

        try:
            record_publication_decision(
                review=review,
                decision=decision["decision"],
                actor=request.user,
                reason=decision.get("reason", ""),
            )
        except ValueError as exc:
            return error_response("decision_refused", str(exc), 409)

        review.refresh_from_db()
        return Response(serialize_review(review))
