import pytest

from catalog.models import AcademicDomain, Author, Document, DocumentAuthor
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_processing.services import attach_extracted_text, create_page_records
from search_discovery.services import rebuild_document_search_index


def create_document(
    *,
    slug,
    title,
    domain_slug="education",
    domain_name="Education",
    abstract="",
    language_code="fr",
    publication_year=2026,
    access_model=Document.AccessModel.FREE,
):
    domain, _ = AcademicDomain.objects.get_or_create(
        slug=domain_slug,
        defaults={"name": domain_name},
    )
    return Document.objects.create(
        title=title,
        slug=slug,
        abstract=abstract,
        language_code=language_code,
        publication_year=publication_year,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )


def add_author(document, display_name, position=1):
    author = Author.objects.create(
        display_name=display_name,
        normalized_name=display_name.lower(),
    )
    DocumentAuthor.objects.create(document=document, author=author, position=position)
    return author


def add_processed_text(document, text):
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
    attach_extracted_text(page=page, text=text, language_code=document.language_code)
    return page


@pytest.mark.django_db
def test_search_documents_api_returns_public_results(client):
    document = create_document(
        slug="api-pedagogie",
        title="Pedagogie universitaire",
        abstract="Formation des enseignants chercheurs.",
    )
    add_author(document, "Aline NZE")
    add_processed_text(document, "Texte interne protege par le lecteur.")
    rebuild_document_search_index(document)

    response = client.get("/search/documents/?q=pedagogie")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    result = payload["results"][0]
    assert result["document_id"] == document.pk
    assert result["title"] == "Pedagogie universitaire"
    assert result["authors"] == ["Aline NZE"]
    assert "page_text" not in result
    assert "Texte interne protege par le lecteur." not in result.values()
    assert "storage_key" not in result
    assert "url" not in result
    assert "session_key" not in result


@pytest.mark.django_db
def test_search_documents_api_returns_restricted_metadata_without_page_text(client):
    document = create_document(
        slug="api-restricted",
        title="Archives hospitalieres",
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    add_processed_text(document, "Diagnostic confidentiel dans le texte interne.")
    rebuild_document_search_index(document)

    response = client.get("/search/documents/?q=Diagnostic")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    result = payload["results"][0]
    assert result["document_id"] == document.pk
    assert result["access_model"] == Document.AccessModel.SUBSCRIPTION
    assert result["text_match"] is True
    assert "Diagnostic confidentiel dans le texte interne." not in result.values()


@pytest.mark.django_db
def test_search_documents_api_applies_filters_and_limit(client):
    matching = create_document(
        slug="api-filter-match",
        title="Archive numerique gabonaise",
        domain_slug="archives",
        domain_name="Archives",
        language_code="fr",
        publication_year=2026,
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    rebuild_document_search_index(matching)
    rebuild_document_search_index(
        create_document(slug="api-filter-other", title="Autre archive", domain_slug="droit", domain_name="Droit")
    )

    response = client.get(
        "/search/documents/?domain=archives&language=fr&access=subscription&year=2026&limit=1"
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["document_id"] == matching.pk


@pytest.mark.parametrize(
    ("query_string", "error_code"),
    [
        ("year=vingt", "invalid_year"),
        ("year=0", "invalid_year"),
        ("limit=abc", "invalid_limit"),
        ("limit=0", "invalid_limit"),
        (f"q={'a' * 121}", "invalid_query"),
    ],
)
@pytest.mark.django_db
def test_search_documents_api_rejects_invalid_numeric_filters(client, query_string, error_code):
    response = client.get(f"/search/documents/?{query_string}")

    assert response.status_code == 400
    assert response.json() == {"error": error_code}
