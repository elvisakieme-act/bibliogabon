from __future__ import annotations

from django.conf import settings
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
    get_reader_manifest,
    get_reader_page,
    get_reader_page_image,
    get_reader_page_image_info,
    get_reader_page_tile_key,
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


def public_url(request, path: str) -> str:
    """Adresse absolue qu'un navigateur peut réellement atteindre.

    Le manifeste IIIF annonce des adresses absolues, et le visualiseur
    construit toutes ses requêtes à partir d'elles. Derrière un proxy inverse,
    `build_absolute_uri` rend l'adresse interne du serveur : le manifeste
    s'affiche et pas une seule image ne charge.
    """
    base = getattr(settings, "PUBLIC_API_BASE_URL", "")
    if base:
        return f"{base}{path}"
    return request.build_absolute_uri(path)


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
            # Le service IIIF quand la page est tuilée : c'est lui que le
            # visualiseur préfère, `image` ne restant qu'un repli simple.
            payload["iiif"] = (
                f"/api/v1/reader/sessions/{session.session_key}"
                f"/pages/{payload['page_number']}/iiif/info.json"
                if payload["image"] is not None
                else None
            )
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


class ReaderImageServiceMixin:
    """Ce que les vues d'image IIIF partagent : retrouver la session, refuser.

    La session est retrouvée et vérifiée exactement comme pour le texte. Une
    seconde écriture de ce contrôle finirait par diverger, et c'est l'image —
    le contenu lui-même — qui serait du mauvais côté.
    """

    def resolve_session(self, request, session_key):
        try:
            session = ReaderSession.objects.select_related("user", "document", "version").get(
                session_key=session_key
            )
        except ReaderSession.DoesNotExist:
            return None, error_response(
                "not_found", "Reader session not found.", status.HTTP_404_NOT_FOUND
            )
        if session.user_id and session.user_id != getattr(request.user, "pk", None):
            return None, error_response(
                "access_denied",
                "This session belongs to another user.",
                status.HTTP_403_FORBIDDEN,
            )
        return session, None

    def refusal(self, exception):
        if isinstance(exception, ReaderSessionInactive):
            return error_response(
                "session_inactive", "Reader session is inactive.", status.HTTP_403_FORBIDDEN
            )
        if isinstance(exception, ReaderAccessDenied):
            return error_response(
                "entitlement_required",
                "An active read entitlement is required.",
                status.HTTP_403_FORBIDDEN,
            )
        return error_response("not_found", "Page not found.", status.HTTP_404_NOT_FOUND)


class ReaderManifestView(ReaderImageServiceMixin, APIView):
    """Manifeste IIIF Presentation 3.0 de la session de lecture.

    Une requête, et le visualiseur sait tout ce qu'il faut pour ouvrir le
    document. Sans lui, mettre 157 pages en page demanderait 157 `info.json`
    — donc 157 autorisations, et le document entier journalisé comme lu avant
    que le lecteur ait tourné une page.
    """

    @extend_schema(
        tags=["Reader"],
        summary="IIIF Presentation manifest for a reader session",
        description=(
            "One request describing every page of the document: dimensions and "
            "image service address. It carries no content — the tiles stay "
            "behind the same authorisation as the page text."
        ),
        operation_id="v1_reader_manifest",
        responses={
            200: OpenApiResponse(description="IIIF Presentation API 3.0 manifest"),
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, session_key):
        session, refusal = self.resolve_session(request, session_key)
        if refusal is not None:
            return refusal
        try:
            manifest = get_reader_manifest(
                session=session,
                base_url=public_url(request, f"/api/v1/reader/sessions/{session_key}"),
            )
        except (ReaderSessionInactive, ReaderAccessDenied, ReaderPageUnavailable) as exc:
            return self.refusal(exc)
        response = Response(manifest, status=status.HTTP_200_OK)
        response["Cache-Control"] = "private, no-store"
        return response


class ReaderPageImageInfoView(ReaderImageServiceMixin, APIView):
    """`info.json` d'une page, au sens de l'Image API 3.0.

    Le visualiseur ne demande que ce qui est déclaré ici : tailles et facteurs
    d'échelle produits à l'ingestion. C'est le contrat entre le tuilage et
    l'écran.
    """

    @extend_schema(
        tags=["Reader"],
        summary="IIIF Image API information for a reader page",
        description=(
            "Level 0 image information for one page, under the same "
            "authorisation as its text: a live reader session and a valid read "
            "entitlement. The identifier points back at this API, never at a "
            "storage location."
        ),
        operation_id="v1_reader_page_image_info",
        responses={
            200: OpenApiResponse(description="IIIF Image API 3.0 info.json"),
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, session_key, page_number: int):
        session, refusal = self.resolve_session(request, session_key)
        if refusal is not None:
            return refusal
        try:
            info = get_reader_page_image_info(
                session=session,
                page_number=page_number,
                identifier=public_url(
                    request, f"/api/v1/reader/sessions/{session_key}/pages/{page_number}/iiif"
                ),
            )
        except (ReaderSessionInactive, ReaderAccessDenied, ReaderPageUnavailable) as exc:
            return self.refusal(exc)
        response = Response(info, status=status.HTTP_200_OK)
        response["Cache-Control"] = "private, no-store"
        return response


class ReaderPageTileView(ReaderImageServiceMixin, APIView):
    """Une tuile IIIF, diffusée sous session de lecture.

    Le chemin reçu n'est jamais concaténé tel quel : la clé de stockage est
    reconstruite à partir des quatre composantes de l'Image API, faute de quoi
    un `../` sortirait de l'arborescence de la page.
    """

    @extend_schema(
        tags=["Reader"],
        summary="Serve a IIIF tile of a reader page",
        description=(
            "One tile of a page, under the same authorisation as its text. The "
            "path follows the IIIF Image API; only rotation 0 and the default "
            "WebP quality exist at level 0. No storage key, bucket or object "
            "name ever appears in the URL or the headers."
        ),
        operation_id="v1_reader_page_tile",
        responses={
            200: OpenApiResponse(description="WebP tile"),
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(
        self,
        request,
        session_key,
        page_number: int,
        region,
        size,
        rotation,
        quality,
        image_format,
    ):
        session, refusal = self.resolve_session(request, session_key)
        if refusal is not None:
            return refusal
        try:
            storage_key = get_reader_page_tile_key(
                session=session,
                page_number=page_number,
                region=region,
                size=size,
                rotation=rotation,
                quality=quality,
                image_format=image_format,
            )
        except (ReaderSessionInactive, ReaderAccessDenied, ReaderPageUnavailable) as exc:
            return self.refusal(exc)

        try:
            stream = open_stream(storage_key)
        except Exception:
            # Une tuile que `info.json` n'annonce pas, ou une page tuilée à une
            # autre résolution : 404, jamais une erreur serveur.
            return error_response("not_found", "Tile not found.", status.HTTP_404_NOT_FOUND)

        response = FileResponse(stream, content_type="image/webp")
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
