from __future__ import annotations

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.errors import error_response
from api.v1.pagination import StandardResultsSetPagination
from api.v1.serializers import (
    ErrorResponseSerializer,
    FavoriteCreateSerializer,
    FavoritePageSerializer,
    FavoriteSerializer,
    ReadingProgressPageSerializer,
    ReadingProgressSerializer,
    ReadingProgressUpdateSerializer,
    document_metadata_prefetches,
    serialize_document_metadata,
)
from catalog.models import Document
from document_reader.exceptions import ReaderAccessDenied, ReaderPageUnavailable
from document_reader.models import FavoriteDocument, ReadingProgress
from document_reader.services import (
    favorite_document,
    readable_document_ids_for_user,
    record_reading_progress,
    remove_favorite,
)


class FavoriteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Personal Library"],
        summary="List the current user's favorites",
        responses={
            200: FavoritePageSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Favorite page",
                value={"count": 0, "next": None, "previous": None, "results": []},
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request):
        favorites = (
            FavoriteDocument.objects.select_related(
                "document", "document__academic_domain", "document__owner_organization"
            )
            .prefetch_related(*document_metadata_prefetches(prefix="document__"))
            .filter(
                user=request.user,
                document__publication_status=Document.PublicationStatus.PUBLISHED,
            )
            .exclude(document__access_model=Document.AccessModel.PRIVATE)
        )
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(favorites, request, view=self)
        readable_document_ids = readable_document_ids_for_user(
            request.user,
            [favorite.document for favorite in page],
        )
        return paginator.get_paginated_response(
            [
                {
                    "document": serialize_document_metadata(
                        favorite.document,
                        user=request.user,
                        readable_document_ids=readable_document_ids,
                    ),
                    "created_at": favorite.created_at.isoformat(),
                }
                for favorite in page
            ]
        )

    @extend_schema(
        tags=["Personal Library"],
        summary="Add a document to the current user's favorites",
        request=FavoriteCreateSerializer,
        responses={
            201: FavoriteSerializer,
            200: FavoriteSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            415: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Favorite request",
                value={"document_id": 1},
                request_only=True,
            ),
            OpenApiExample(
                "Favorite created",
                value={
                    "document": {
                        "id": 1,
                        "slug": "droit-public",
                        "title": "Droit public",
                        "abstract": "",
                        "language_code": "fr",
                        "publication_year": 2026,
                        "document_type": "open_resource",
                        "access_model": "free",
                        "domain": None,
                        "authors": [],
                        "owner": None,
                        "page_count": 120,
                        "cover": None,
                        "access": {
                            "can_read": True,
                            "access_model": "free",
                            "reason": "free",
                        },
                    },
                    "created_at": "2026-07-29T16:00:00Z",
                },
                response_only=True,
                status_codes=["201"],
            )
        ],
    )
    def post(self, request):
        document_id = request.data.get("document_id")
        try:
            document = Document.objects.get(pk=document_id)
        except (TypeError, ValueError, Document.DoesNotExist):
            return error_response("not_found", "Document not found.", status.HTTP_404_NOT_FOUND)
        try:
            favorite, created = favorite_document(request.user, document)
        except ReaderAccessDenied:
            return error_response("not_found", "Document not found.", status.HTTP_404_NOT_FOUND)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            {
                "document": serialize_document_metadata(favorite.document, user=request.user),
                "created_at": favorite.created_at.isoformat(),
            },
            status=status_code,
        )


class FavoriteDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Personal Library"], summary="Remove a document from the current user's favorites", responses={204: None, 401: ErrorResponseSerializer})
    def delete(self, request, document_id: int):
        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        remove_favorite(request.user, document)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadingProgressListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Personal Library"],
        summary="List the current user's reading progress",
        responses={
            200: ReadingProgressPageSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Reading progress page",
                value={"count": 0, "next": None, "previous": None, "results": []},
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request):
        progress_rows = (
            ReadingProgress.objects.select_related(
                "document", "document__academic_domain", "document__owner_organization"
            )
            .prefetch_related(*document_metadata_prefetches(prefix="document__"))
            .filter(
                user=request.user,
                document__publication_status=Document.PublicationStatus.PUBLISHED,
            )
            .exclude(document__access_model=Document.AccessModel.PRIVATE)
        )
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(progress_rows, request, view=self)
        readable_document_ids = readable_document_ids_for_user(
            request.user,
            [progress.document for progress in page],
        )
        return paginator.get_paginated_response(
            [
                {
                    "document": serialize_document_metadata(
                        progress.document,
                        user=request.user,
                        readable_document_ids=readable_document_ids,
                    ),
                    "last_page_number": progress.last_page_number,
                    "updated_at": progress.updated_at.isoformat(),
                }
                for progress in page
            ]
        )


class ReadingProgressUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Personal Library"],
        summary="Update the current user's reading progress",
        request=ReadingProgressUpdateSerializer,
        responses={
            200: ReadingProgressSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            415: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Reading progress request",
                value={"last_page_number": 4},
                request_only=True,
            ),
            OpenApiExample(
                "Reading progress updated",
                value={
                    "document": {
                        "id": 1,
                        "slug": "droit-public",
                        "title": "Droit public",
                        "abstract": "",
                        "language_code": "fr",
                        "publication_year": 2026,
                        "document_type": "open_resource",
                        "access_model": "free",
                        "domain": None,
                        "authors": [],
                        "owner": None,
                        "page_count": 120,
                        "cover": None,
                        "access": {
                            "can_read": True,
                            "access_model": "free",
                            "reason": "free",
                        },
                    },
                    "last_page_number": 4,
                    "updated_at": "2026-07-29T16:00:00Z",
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def patch(self, request, document_id: int):
        try:
            page_number = int(request.data.get("last_page_number"))
        except (TypeError, ValueError):
            return error_response(
                "invalid_page_number",
                "last_page_number must be a positive integer.",
                status.HTTP_400_BAD_REQUEST,
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
            progress = record_reading_progress(request.user, document, page_number)
        except Document.DoesNotExist:
            return error_response("not_found", "Document not found.", status.HTTP_404_NOT_FOUND)
        except ReaderPageUnavailable as exc:
            message = f"{str(exc).rstrip('.')}."
            return error_response("invalid_page_number", message, status.HTTP_400_BAD_REQUEST)
        except ReaderAccessDenied:
            return error_response("entitlement_required", "An active read entitlement is required.", status.HTTP_403_FORBIDDEN)
        return Response(
            {
                "document": serialize_document_metadata(progress.document, user=request.user),
                "last_page_number": progress.last_page_number,
                "updated_at": progress.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
