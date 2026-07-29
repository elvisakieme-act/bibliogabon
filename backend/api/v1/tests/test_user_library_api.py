import pytest
from django.contrib.auth import get_user_model
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Entitlement
from catalog.models import AcademicDomain, Author, Document, DocumentAuthor
from document_ingestion.models import DocumentVersion
from document_reader.models import FavoriteDocument, ReadingProgress


def auth_headers(client):
    response = client.post(
        "/api/v1/auth/register/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {response.json()['tokens']['access']}"}


def create_document(
    slug="favorite-doc",
    access_model=Document.AccessModel.FREE,
    publication_status=Document.PublicationStatus.PUBLISHED,
    page_count=10,
):
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
        publication_status=publication_status,
    )
    DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=page_count,
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


@pytest.mark.django_db
def test_reading_progress_requires_entitlement_for_restricted_document():
    client = APIClient()
    headers = auth_headers(client)
    document = create_document(access_model=Document.AccessModel.SUBSCRIPTION)

    response = client.patch(
        f"/api/v1/me/reading-progress/{document.pk}/",
        {"last_page_number": 1},
        format="json",
        **headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "entitlement_required"
    assert not ReadingProgress.objects.exists()


@pytest.mark.django_db
def test_reading_progress_accepts_entitled_user_for_restricted_document():
    client = APIClient()
    headers = auth_headers(client)
    user = get_user_model().objects.get(email="reader@example.ga")
    document = create_document(access_model=Document.AccessModel.SUBSCRIPTION)
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.ADMIN_GRANT,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=document.entitlement_scope_id,
        starts_at=timezone.now() - timezone.timedelta(minutes=1),
        ends_at=timezone.now() + timezone.timedelta(minutes=1),
    )

    response = client.patch(
        f"/api/v1/me/reading-progress/{document.pk}/",
        {"last_page_number": 1},
        format="json",
        **headers,
    )

    assert response.status_code == 200
    assert ReadingProgress.objects.get(user=user, document=document).last_page_number == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("access_model", "publication_status"),
    [
        (Document.AccessModel.PRIVATE, Document.PublicationStatus.PUBLISHED),
        (Document.AccessModel.FREE, Document.PublicationStatus.DRAFT),
    ],
)
def test_favorite_rejects_private_and_unpublished_documents(access_model, publication_status):
    client = APIClient()
    headers = auth_headers(client)
    document = create_document(access_model=access_model, publication_status=publication_status)

    response = client.post("/api/v1/me/favorites/", {"document_id": document.pk}, format="json", **headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert not FavoriteDocument.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("page_number", [0, 11])
def test_reading_progress_rejects_page_outside_current_version(page_number):
    client = APIClient()
    headers = auth_headers(client)
    document = create_document(page_count=10)

    response = client.patch(
        f"/api/v1/me/reading-progress/{document.pk}/",
        {"last_page_number": page_number},
        format="json",
        **headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_page_number"
    assert not ReadingProgress.objects.exists()


@pytest.mark.django_db
def test_favorites_list_serializes_multiple_documents_in_constant_query_count():
    client = APIClient()
    headers = auth_headers(client)
    user = get_user_model().objects.get(email="reader@example.ga")
    documents = [create_document(slug=f"favorite-doc-{number}") for number in range(2)]
    for number, document in enumerate(documents):
        author = Author.objects.create(display_name=f"Author {number}", normalized_name=f"author {number}")
        DocumentAuthor.objects.create(document=document, author=author, position=1)
        FavoriteDocument.objects.create(user=user, document=document)

    with CaptureQueriesContext(connection) as queries:
        response = client.get("/api/v1/me/favorites/", **headers)

    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert len(queries) == 5
