from __future__ import annotations

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.covers import cover_url_for, documents_with_cover
from api.v1.errors import error_response
from api.v1.pagination import StandardResultsSetPagination
from api.v1.serializers import (
    AuthorMetadataPageSerializer,
    DocumentMetadataPageSerializer,
    DocumentMetadataSerializer,
    DocumentTypePageSerializer,
    DomainPageSerializer,
    ErrorResponseSerializer,
    SearchResultPageSerializer,
    document_metadata_prefetches,
    serialize_document_metadata,
)
from catalog.models import AcademicDomain, Author, Document, DocumentType
from document_reader.services import readable_document_ids_for_user
from search_discovery.services import search_documents


def _published_documents():
    return (
        Document.objects.select_related(
            "academic_domain", "owner_organization", "document_type"
        )
        .prefetch_related(*document_metadata_prefetches())
        .filter(publication_status=Document.PublicationStatus.PUBLISHED)
        .exclude(access_model=Document.AccessModel.PRIVATE)
        .order_by("title", "id")
    )


class DocumentListView(APIView):
    @extend_schema(
        tags=["Catalog"],
        summary="List public catalog documents",
        description="Responses expose public metadata only and never include raw files, storage keys, signed URLs, or OCR full text.",
        operation_id="v1_catalog_documents_list",
        responses={
            200: DocumentMetadataPageSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Catalog page",
                value={"count": 0, "next": None, "previous": None, "results": []},
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request):
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(_published_documents(), request, view=self)
        readable_document_ids = readable_document_ids_for_user(request.user, page)
        document_ids_with_cover = documents_with_cover(page)
        results = [
            serialize_document_metadata(
                document,
                user=request.user,
                readable_document_ids=readable_document_ids,
                document_ids_with_cover=document_ids_with_cover,
            )
            for document in page
        ]
        return paginator.get_paginated_response(results)


class DocumentDetailView(APIView):
    @extend_schema(
        tags=["Catalog"],
        summary="Retrieve a public catalog document",
        description="Responses expose public metadata only and never include raw files, storage keys, signed URLs, or OCR full text.",
        operation_id="v1_catalog_documents_retrieve",
        responses={
            200: DocumentMetadataSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Catalog document",
                value={
                    "id": 1,
                    "slug": "droit-public",
                    "title": "Droit public",
                    "abstract": "Introduction au droit public gabonais.",
                    "language_code": "fr",
                    "publication_year": 2026,
                    "document_type": {
                        "id": 3,
                        "name": "Thèse",
                        "slug": "these",
                        "icon": "graduation-cap",
                        "color": "#2563EB",
                    },
                    "category": "open_resource",
                    "access_model": "free",
                    "domain": {"id": 1, "name": "Droit", "slug": "droit"},
                    "authors": [],
                    "owner": None,
                    "page_count": 120,
                    "cover": "/api/v1/catalog/documents/12/cover/",
                    "access": {
                        "can_read": True,
                        "access_model": "free",
                        "reason": "free",
                    },
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request, document_id: int):
        try:
            document = _published_documents().get(pk=document_id)
        except Document.DoesNotExist:
            return error_response(
                code="not_found",
                message="Document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        readable_document_ids = readable_document_ids_for_user(request.user, [document])
        document_ids_with_cover = documents_with_cover([document])
        return Response(
            serialize_document_metadata(
                document,
                user=request.user,
                readable_document_ids=readable_document_ids,
                document_ids_with_cover=document_ids_with_cover,
            ),
            status=status.HTTP_200_OK,
        )


class DomainListView(APIView):
    @extend_schema(
        tags=["Catalog"],
        summary="List active academic domains",
        description="Responses expose public metadata only and never include raw files, storage keys, signed URLs, or OCR full text.",
        responses={
            200: DomainPageSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Domain page",
                value={
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [{"id": 1, "name": "Droit", "slug": "droit"}],
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request):
        domains = AcademicDomain.objects.filter(is_active=True).order_by("name", "id")
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(domains, request, view=self)
        return paginator.get_paginated_response(
            [{"id": domain.pk, "name": domain.name, "slug": domain.slug} for domain in page]
        )


class DocumentTypeListView(APIView):
    @extend_schema(
        tags=["Catalog"],
        summary="List active document types",
        description="Types de documents disponibles (cours, thèse, examen…) avec leur icône et couleur, pour alimenter les filtres du frontend.",
        responses={
            200: DocumentTypePageSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Document type page",
                value={
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 3,
                            "name": "Thèse",
                            "slug": "these",
                            "icon": "graduation-cap",
                            "color": "#2563EB",
                        }
                    ],
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request):
        types = DocumentType.objects.filter(is_active=True).order_by(
            "display_order", "name", "id"
        )
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(types, request, view=self)
        return paginator.get_paginated_response(
            [
                {
                    "id": document_type.pk,
                    "name": document_type.name,
                    "slug": document_type.slug,
                    "icon": document_type.icon,
                    "color": document_type.color,
                }
                for document_type in page
            ]
        )


class AuthorListView(APIView):
    @extend_schema(
        tags=["Catalog"],
        summary="List public catalog authors",
        description="Responses expose public metadata only and never include raw files, storage keys, signed URLs, or OCR full text.",
        responses={
            200: AuthorMetadataPageSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Author page",
                value={
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "display_name": "Aline NZE",
                            "author_type": "person",
                        }
                    ],
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request):
        authors = (
            Author.objects.filter(document_authorships__document__in=_published_documents())
            .distinct()
            .order_by("normalized_name", "display_name", "id")
        )
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(authors, request, view=self)
        return paginator.get_paginated_response(
            [
                {
                    "id": author.pk,
                    "display_name": author.display_name,
                    "author_type": author.author_type,
                }
                for author in page
            ]
        )


def _with_covers(results: list[dict]) -> list[dict]:
    """Ajoute l'adresse de couverture à des résultats de recherche.

    La recherche a son propre sérialiseur : elle ne passe pas par
    `serialize_document_metadata`, et l'écran de résultats restait donc
    entièrement gris pendant que le catalogue affichait ses couvertures.

    L'enrichissement se fait ici, dans la couche API, et non dans
    `search_discovery` : la découvrabilité est une règle du lecteur, et un
    service de recherche qui l'importerait en tiendrait une seconde copie.
    """
    if not results:
        return results
    documents = {
        document.pk: document
        for document in Document.objects.filter(pk__in=[r["id"] for r in results])
    }
    with_cover = documents_with_cover(documents.values())
    for result in results:
        document = documents.get(result["id"])
        result["cover"] = cover_url_for(document, with_cover) if document else None
    return results


class SearchView(APIView):
    @extend_schema(
        tags=["Search"],
        summary="Search the public catalog",
        description="Responses expose public metadata only and never include raw files, storage keys, signed URLs, or OCR full text.",
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter(
                "type",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                description="Slug du type de document (cours, these, examen…).",
            ),
            OpenApiParameter("domain", OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter("language", OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter("access", OpenApiTypes.STR, OpenApiParameter.QUERY),
            OpenApiParameter("year", OpenApiTypes.INT, OpenApiParameter.QUERY),
        ],
        responses={
            200: SearchResultPageSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Search page",
                value={"count": 0, "next": None, "previous": None, "results": []},
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request):
        try:
            year = request.query_params.get("year")
            publication_year = int(year) if year else None
        except ValueError:
            return error_response(
                "invalid_year", "year must be an integer.", status.HTTP_400_BAD_REQUEST
            )
        results = search_documents(
            query=request.query_params.get("q", ""),
            type_slug=request.query_params.get("type", ""),
            domain_slug=request.query_params.get("domain", ""),
            language_code=request.query_params.get("language", ""),
            access_model=request.query_params.get("access", ""),
            publication_year=publication_year,
            limit=None,
        )
        normalized = [
            {
                "id": result["document_id"],
                "title": result["title"],
                "slug": result["slug"],
                "abstract": result["abstract"],
                "language_code": result["language_code"],
                "publication_year": result["publication_year"],
                "document_type": result["document_type"],
                "domain": result["academic_domain"],
                "authors": result["authors"],
                "access_model": result["access_model"],
                "indexed_page_count": result["indexed_page_count"],
                "score": result["score"],
                "text_match": result["text_match"],
            }
            for result in results
        ]
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(normalized, request, view=self)
        # La couverture est résolue **après** pagination : la recherche renvoie
        # tous les résultats, et les résoudre tous ferait payer une page de
        # vingt vignettes le prix de plusieurs centaines.
        page = _with_covers(page)
        return paginator.get_paginated_response(page)
