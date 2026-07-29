import pytest
from rest_framework.test import APIClient

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_reader.models import FavoriteDocument, ReadingProgress


def auth_headers(client):
    response = client.post(
        "/api/v1/auth/register/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {response.json()['tokens']['access']}"}


def create_document(slug="favorite-doc", access_model=Document.AccessModel.FREE):
    domain = AcademicDomain.objects.create(name=f"Domain {slug}", slug=f"domain-{slug}")
    document = Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        abstract="Resume public.",
        language_code="fr",
        publication_year=2026,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )
    DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=10,
    )
    return document


@pytest.mark.django_db
def test_favorites_require_authentication():
    client = APIClient()

    response = client.get("/api/v1/me/favorites/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_add_favorite_is_idempotent():
    client = APIClient()
    headers = auth_headers(client)
    document = create_document()

    first = client.post("/api/v1/me/favorites/", {"document_id": document.pk}, format="json", **headers)
    second = client.post("/api/v1/me/favorites/", {"document_id": document.pk}, format="json", **headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert FavoriteDocument.objects.count() == 1


@pytest.mark.django_db
def test_list_favorites_returns_document_metadata():
    client = APIClient()
    headers = auth_headers(client)
    document = create_document()
    client.post("/api/v1/me/favorites/", {"document_id": document.pk}, format="json", **headers)

    response = client.get("/api/v1/me/favorites/", **headers)

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["document"]["id"] == document.pk


@pytest.mark.django_db
def test_delete_favorite_is_idempotent():
    client = APIClient()
    headers = auth_headers(client)
    document = create_document()

    response = client.delete(f"/api/v1/me/favorites/{document.pk}/", **headers)

    assert response.status_code == 204


@pytest.mark.django_db
def test_reading_progress_stores_resume_data_only():
    client = APIClient()
    headers = auth_headers(client)
    document = create_document()

    response = client.patch(
        f"/api/v1/me/reading-progress/{document.pk}/",
        {"last_page_number": 4},
        format="json",
        **headers,
    )

    assert response.status_code == 200
    progress = ReadingProgress.objects.get(document=document)
    assert progress.last_page_number == 4
    payload = response.json()
    assert set(payload) == {"document", "last_page_number", "updated_at"}
    assert "page_access" not in str(payload).lower()
