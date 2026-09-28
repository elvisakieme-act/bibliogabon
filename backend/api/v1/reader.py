from __future__ import annotations

from django.http import FileResponse
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.errors import error_response
from api.v1.serializers import (
    ErrorResponseSerializer,
    ReaderPageSerializer,
    ReaderSessionCreateSerializer,
    ReaderSessionSerializer,
)
from catalog.models import Document
from document_ingestion.blob_storage import open_stream
from document_ingestion.models import DocumentAsset
from document_reader.exceptions import (
    ReaderAccessDenied,
    ReaderPageUnavailable,
    ReaderSessionInactive,
)
from document_reader.models import ReaderSession
from document_reader.services import (
    document_requires_entitlement,
    end_reader_session,
    get_reader_page,
    get_reader_page_image,
    start_reader_session,
)


def _client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:45]
    return request.META.get("REMOTE_ADDR", "")[:45]


def _user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:300]


class ReaderSessionCreateView(APIView):
    @extend_schema(
        tags=["Reader"],
        summary="Start a controlled reader session",
        description="Free documents allow anonymous controlled reader sessions. Restricted documents require JWT authentication and active read entitlement.",
        request=ReaderSessionCreateSerializer,
        responses={
            201: ReaderSessionSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            415: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Reader session request",
                value={"document_id": 1},
                request_only=True,
            ),
            OpenApiExample(
                "Reader session",
                value={
                    "session_key": "550e8400-e29b-41d4-a716-446655440000",
                    "document_id": 1,
                    "version_id": 1,
                    "expires_at": "2026-07-29T18:00:00Z",
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    def post(self, request):
        document_id = request.data.get("document_id")
        if not document_id:
            return error_response(
                code="document_required",
                message="document_id is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors={"document_id": ["This field is required."]},
            )
        try:
            document = (
                Document.objects.filter(
                    pk=document_id,
                    publication_status=Document.PublicationStatus.PUBLISHED,
                )
                .exclude(access_model=Document.AccessModel.PRIVATE)
                .get()
            )
        except (TypeError, ValueError, Document.DoesNotExist):
            return error_response(
                code="not_found",
                message="Document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        user = request.user if request.user.is_authenticated else None
        if document_requires_entitlement(document) and user is None:
            return error_response(
                code="authentication_required",
                message="Authentication is required for this document.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            session = start_reader_session(
                user=user,
                document=document,
                client_ip=_client_ip(request),
                user_agent=_user_agent(request),
            )
        except ReaderAccessDenied:
            return error_response(
                code="entitlement_required",
                message="An active read entitlement is required.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {
                "session_key": str(session.session_key),
                "document_id": session.document_id,
                "version_id": session.version_id,
                "expires_at": session.expires_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


def _page_image_url(session: ReaderSession, page_number: int) -> str | None:
    """Adresse de l'image de la page, ou `None` si elle n'a pas été rendue.

    Annoncer une adresse pour une page sans rendu ferait demander au lecteur
    une image inexistante à chaque page d'un document dont le rendu a échoué.
    Mieux vaut qu'il sache d'avance et affiche le texte.

    L'adresse est construite ici, dans la couche API, et non par le service :
    celui-ci sert deux surfaces HTTP aux espaces d'URL différents.
    """
    has_image = DocumentAsset.objects.filter(
        page__version=session.version,
        page__page_number=page_number,
        asset_type=DocumentAsset.AssetType.PAGE_IMAGE,
    ).exists()
    if not has_image:
        return None
    return f"/api/v1/reader/sessions/{session.session_key}/pages/{page_number}/image/"


class ReaderPageView(APIView):
    @extend_schema(
        tags=["Reader"],
        summary="Retrieve a controlled reader page",
        description="Free documents allow anonymous controlled reader sessions. Restricted documents require JWT authentication and active read entitlement.",
        responses={
            200: ReaderPageSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Reader page",
                value={
                    "session_key": "550e8400-e29b-41d4-a716-446655440000",
                    "document_id": 1,
                    "version_id": 1,
                    "page_number": 1,
                    "page_count": 120,
                    "language_code": "fr",
                    "text": "Contenu controle de la page.",
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request, session_key, page_number: int):
        try:
            session = ReaderSession.objects.select_related("user", "document", "version").get(
                session_key=session_key
            )
        except ReaderSession.DoesNotExist:
            return error_response(
                "not_found", "Reader session not found.", status.HTTP_404_NOT_FOUND
            )
        if session.user_id and session.user_id != getattr(request.user, "pk", None):
            return error_response(
                "access_denied",
                "This session belongs to another user.",
                status.HTTP_403_FORBIDDEN,
            )
        try:
            payload = get_reader_page(session=session, page_number=page_number)
            payload["image"] = _page_image_url(session, payload["page_number"])
            return Response(payload, status=status.HTTP_200_OK)
        except ReaderSessionInactive:
            return error_response(
                "session_inactive", "Reader session is inactive.", status.HTTP_403_FORBIDDEN
            )
        except ReaderAccessDenied:
            return error_response(
                "entitlement_required",
                "An active read entitlement is required.",
                status.HTTP_403_FORBIDDEN,
            )
        except ReaderPageUnavailable:
            return error_response("not_found", "Page not found.", status.HTTP_404_NOT_FOUND)


class ReaderPageImageView(APIView):
    """Image fidèle d'une page, diffusée sous session de lecture.

    Le rendu de la page est produit à chaque ingestion et n'était jamais servi.
    Son docstring disait pourtant, depuis le premier jour, qu'il « n'est servi
    qu'à travers une session de lecture autorisée » — c'est ce que cette vue
    met enfin en œuvre.

    Comme pour la couverture, l'adresse est opaque : ni clé de stockage, ni
    seau, ni nom d'objet, ni dans l'URL ni dans les en-têtes. À la différence
    de la couverture, elle exige une session vivante et un droit de lecture
    valide, puisqu'elle livre le contenu lui-même et non une vignette
    publique.
    """

    @extend_schema(
        tags=["Reader"],
        summary="Serve the rendered image of a reader page",
        description=(
            "The page as it was laid out, streamed through an opaque path under "
            "the same authorisation as its text: a live reader session and a "
            "valid read entitlement. No storage key, bucket or object name ever "
            "appears in the URL or the headers. A page whose image is missing "
            "returns 404, so the reader can fall back to text."
        ),
        operation_id="v1_reader_page_image",
        responses={
            200: OpenApiResponse(description="WebP image of the page"),
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, session_key, page_number: int):
        try:
            session = ReaderSession.objects.select_related("user", "document", "version").get(
                session_key=session_key
            )
        except ReaderSession.DoesNotExist:
            return error_response(
                "not_found", "Reader session not found.", status.HTTP_404_NOT_FOUND
            )
        if session.user_id and session.user_id != getattr(request.user, "pk", None):
            return error_response(
                "access_denied",
                "This session belongs to another user.",
                status.HTTP_403_FORBIDDEN,
            )
        try:
            asset = get_reader_page_image(session=session, page_number=page_number)
        except ReaderSessionInactive:
            return error_response(
                "session_inactive", "Reader session is inactive.", status.HTTP_403_FORBIDDEN
            )
        except ReaderAccessDenied:
            return error_response(
                "entitlement_required",
                "An active read entitlement is required.",
                status.HTTP_403_FORBIDDEN,
            )
        except ReaderPageUnavailable:
            return error_response("not_found", "Page not found.", status.HTTP_404_NOT_FOUND)

        response = FileResponse(
            open_stream(asset.storage_key),
            content_type=asset.mime_type or "image/webp",
        )
        # `FileResponse` nomme le fichier d'après le flux, ce qui ferait
        # apparaître la clé de stockage dans un en-tête. On impose le nôtre.
        response.headers["Content-Disposition"] = f'inline; filename="page-{page_number}.webp"'
        # Privé : une page lue n'est pas une couverture publique, et un cache
        # partagé la servirait à qui n'a pas de session.
        response.headers["Cache-Control"] = "private, no-store"
        return response


class ReaderSessionDeleteView(APIView):
    @extend_schema(
        tags=["Reader"],
        summary="End a controlled reader session",
        description="Free documents allow anonymous controlled reader sessions. Restricted documents require JWT authentication and active read entitlement.",
        responses={
            204: None,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
    )
    def delete(self, request, session_key):
        try:
            session = ReaderSession.objects.get(session_key=session_key)
        except ReaderSession.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if session.user_id and session.user_id != getattr(request.user, "pk", None):
            return error_response(
                "access_denied",
                "This session belongs to another user.",
                status.HTTP_403_FORBIDDEN,
            )
        end_reader_session(session=session)
        return Response(status=status.HTTP_204_NO_CONTENT)
