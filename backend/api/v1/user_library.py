from __future__ import annotations

from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
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
    serialize_document_metadata,
)
from catalog.models import Document, DocumentAuthor
from document_ingestion.models import DocumentVersion
from document_reader.exceptions import ReaderAccessDenied, ReaderPageUnavailable
from document_reader.models import FavoriteDocument, ReadingProgress
from document_reader.services import favorite_document, record_reading_progress, remove_favorite


def _metadata_prefetches():
    return [
        Prefetch(
            "document__document_authors",
            queryset=DocumentAuthor.objects.select_related("author").order_by("position"),
            to_attr="_api_document_authors",
        ),
        Prefetch(
            "document__versions",
            queryset=DocumentVersion.objects.filter(is_current=True).order_by("-created_at"),
            to_attr="_api_current_versions",
        ),
    ]


class FavoriteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Personal Library"], responses={200: FavoritePageSerializer, 401: ErrorResponseSerializer})
    def get(self, request):
        favorites = (
            FavoriteDocument.objects.select_related(
                "document", "document__academic_domain", "document__owner_organization"
            )
            .prefetch_related(*_metadata_prefetches())
            .filter(
                user=request.user,
                document__publication_status=Document.PublicationStatus.PUBLISHED,
            )
            .exclude(document__access_model=Document.AccessModel.PRIVATE)
        )
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(favorites, request, view=self)
        return paginator.get_paginated_response(
            [
                {
                    "document": serialize_document_metadata(favorite.document, user=request.user),
                    "created_at": favorite.created_at.isoformat(),
                }
                for favorite in page
            ]
        )

    @extend_schema(
        tags=["Personal Library"],
        request=FavoriteCreateSerializer,
        responses={201: FavoriteSerializer, 200: FavoriteSerializer, 401: ErrorResponseSerializer, 404: ErrorResponseSerializer},
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

    @extend_schema(tags=["Personal Library"], responses={204: None, 401: ErrorResponseSerializer})
    def delete(self, request, document_id: int):
        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        remove_favorite(request.user, document)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadingProgressListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Personal Library"], responses={200: ReadingProgressPageSerializer, 401: ErrorResponseSerializer})
    def get(self, request):
        progress_rows = (
            ReadingProgress.objects.select_related(
                "document", "document__academic_domain", "document__owner_organization"
            )
            .prefetch_related(*_metadata_prefetches())
            .filter(
                user=request.user,
                document__publication_status=Document.PublicationStatus.PUBLISHED,
            )
            .exclude(document__access_model=Document.AccessModel.PRIVATE)
        )
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(progress_rows, request, view=self)
        return paginator.get_paginated_response(
            [
                {
                    "document": serialize_document_metadata(progress.document, user=request.user),
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
        request=ReadingProgressUpdateSerializer,
        responses={200: ReadingProgressSerializer, 400: ErrorResponseSerializer, 401: ErrorResponseSerializer, 403: ErrorResponseSerializer, 404: ErrorResponseSerializer},
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
            document = Document.objects.get(pk=document_id)
            progress = record_reading_progress(request.user, document, page_number)
        except Document.DoesNotExist:
            return error_response("not_found", "Document not found.", status.HTTP_404_NOT_FOUND)
        except ReaderPageUnavailable:
            return error_response("invalid_page_number", "last_page_number must be positive.", status.HTTP_400_BAD_REQUEST)
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
