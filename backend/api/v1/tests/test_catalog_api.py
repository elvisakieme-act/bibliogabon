import pytest
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from catalog.models import AcademicDomain, Author, Document, DocumentAuthor
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_processing.services import attach_extracted_text, create_page_records
from search_discovery.services import rebuild_document_search_index


def create_document(
    slug,
    title,
    access_model=Document.AccessModel.FREE,
    status=Document.PublicationStatus.PUBLISHED,
):
    domain, _ = AcademicDomain.objects.get_or_create(slug="droit", defaults={"name": "Droit"})
    document = Document.objects.create(
        title=title,
        slug=slug,
        abstract="Resume public.",
        language_code="fr",
        publication_year=2026,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=status,
    )
    author = Author.objects.create(display_name=f"Auteur {title}", normalized_name=title.lower())
    DocumentAuthor.objects.create(document=document, author=author, position=1)
    version = DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=1,
    )
    page = create_page_records(version=version, page_count=1)[0]
    page.status = DocumentPage.Status.PROCESSED
    page.save(update_fields=["status", "updated_at"])
    attach_extracted_text(page=page, text="Texte interne non expose.", language_code="fr")
    rebuild_document_search_index(document)
    return document


@pytest.mark.django_db
def test_document_list_returns_public_metadata_only():
    client = APIClient()
    document = create_document("droit-public", "Droit public")
    create_document("draft-hidden", "Brouillon", status=Document.PublicationStatus.DRAFT)

    response = client.get("/api/v1/catalog/documents/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    result = payload["results"][0]
    assert result["id"] == document.pk
    assert result["title"] == "Droit public"
    assert result["access"]["can_read"] is True
    assert result["access"]["reason"] == "free"
    assert "Texte interne non expose." not in response.content.decode("utf-8")
    assert "storage_key" not in response.content.decode("utf-8")


@pytest.mark.django_db
def test_restricted_document_detail_public_metadata_requires_auth_for_access():
    client = APIClient()
    document = create_document(
        "restricted",
        "Document restreint",
        access_model=Document.AccessModel.SUBSCRIPTION,
    )

    response = client.get(f"/api/v1/catalog/documents/{document.pk}/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == document.pk
    assert payload["access"] == {
        "can_read": False,
        "access_model": "subscription",
        "reason": "authentication_required",
    }


@pytest.mark.django_db
def test_private_document_detail_returns_404():
    client = APIClient()
    document = create_document("private", "Document prive", access_model=Document.AccessModel.PRIVATE)

    response = client.get(f"/api/v1/catalog/documents/{document.pk}/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_domains_and_authors_endpoints_return_public_values():
    client = APIClient()
    create_document("droit-public", "Droit public")

    domains = client.get("/api/v1/catalog/domains/")
    authors = client.get("/api/v1/catalog/authors/")

    assert domains.status_code == 200
    assert domains.json()["results"][0]["slug"] == "droit"
    assert authors.status_code == 200
    assert authors.json()["results"][0]["display_name"] == "Auteur Droit public"


@pytest.mark.django_db
def test_search_endpoint_uses_standard_pagination_and_hides_page_text():
    client = APIClient()
    document = create_document("searchable", "Recherche pedagogique")

    response = client.get("/api/v1/search/?q=interne")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == document.pk
    assert payload["results"][0]["text_match"] is True
    assert "Texte interne non expose." not in response.content.decode("utf-8")


def test_openapi_schema_documents_catalog_and_search_endpoints():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]

    expected_paths = {
        "/api/v1/catalog/documents/",
        "/api/v1/catalog/documents/{document_id}/",
        "/api/v1/catalog/domains/",
        "/api/v1/catalog/authors/",
        "/api/v1/search/",
    }

    assert expected_paths <= set(paths)

    paginated_endpoints = {
        "/api/v1/catalog/documents/": "DocumentMetadata",
        "/api/v1/catalog/domains/": "Domain",
        "/api/v1/catalog/authors/": "AuthorMetadata",
        "/api/v1/search/": "SearchResult",
    }
    for path, result_schema_name in paginated_endpoints.items():
        response_schema = paths[path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        if "$ref" in response_schema:
            response_schema = schema["components"]["schemas"][response_schema["$ref"].rsplit("/", 1)[-1]]

        assert response_schema["type"] == "object"
        assert {"count", "next", "previous", "results"} <= set(response_schema["properties"])
        assert response_schema["properties"]["results"]["type"] == "array"
        assert response_schema["properties"]["results"]["items"]["$ref"].endswith(
            f"/{result_schema_name}"
        )
