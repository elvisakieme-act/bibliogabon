import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from accounts.models import Entitlement
from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_processing.services import attach_extracted_text, create_page_records
from document_reader.models import ReaderSession


def auth_headers(access_token: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {access_token}"}


def create_user_and_token(client, email="reader@example.ga"):
    response = client.post(
        "/api/v1/auth/register/",
        {"email": email, "password": "StrongPass123!"},
        format="json",
    )
    return response.json()["tokens"]["access"], get_user_model().objects.get(email=email)


def create_readable_document(slug="reader-v1-free", access_model=Document.AccessModel.FREE):
    domain = AcademicDomain.objects.create(name=f"Reader {slug}", slug=f"reader-{slug}")
    document = Document.objects.create(
        title=f"Reader {slug}",
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )
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
    attach_extracted_text(page=page, text="Texte lisible API V1.", language_code="fr")
    return document


@pytest.mark.django_db
def test_anonymous_user_can_create_free_reader_session():
    client = APIClient()
    document = create_readable_document()

    response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document_id"] == document.pk
    assert ReaderSession.objects.get(session_key=payload["session_key"]).user_id is None


@pytest.mark.django_db
def test_anonymous_user_can_read_page_from_free_session():
    client = APIClient()
    document = create_readable_document()
    session_response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
    )
    session_key = session_response.json()["session_key"]

    response = client.get(f"/api/v1/reader/sessions/{session_key}/pages/1/")

    assert response.status_code == 200
    assert response.json()["text"] == "Texte lisible API V1."
    assert "storage_key" not in response.content.decode("utf-8")


@pytest.mark.django_db
def test_anonymous_user_cannot_create_restricted_reader_session():
    client = APIClient()
    document = create_readable_document(access_model=Document.AccessModel.SUBSCRIPTION)

    response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


@pytest.mark.django_db
def test_authenticated_user_without_entitlement_cannot_create_restricted_session():
    client = APIClient()
    access, _ = create_user_and_token(client)
    document = create_readable_document(
        slug="reader-v1-restricted",
        access_model=Document.AccessModel.SUBSCRIPTION,
    )

    response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
        **auth_headers(access),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "entitlement_required"


@pytest.mark.django_db
def test_authenticated_user_with_entitlement_can_create_restricted_session():
    client = APIClient()
    access, user = create_user_and_token(client)
    document = create_readable_document(
        slug="reader-v1-entitled",
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=document.entitlement_scope_id,
        starts_at=timezone.now() - timezone.timedelta(minutes=5),
        ends_at=timezone.now() + timezone.timedelta(minutes=30),
    )

    response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
        **auth_headers(access),
    )

    assert response.status_code == 201
    assert ReaderSession.objects.get(session_key=response.json()["session_key"]).user == user


@pytest.mark.django_db
def test_delete_reader_session_returns_204():
    client = APIClient()
    document = create_readable_document()
    session_response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
    )

    response = client.delete(
        f"/api/v1/reader/sessions/{session_response.json()['session_key']}/"
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_authenticated_user_cannot_read_another_users_reader_session():
    client = APIClient()
    owner_access, _ = create_user_and_token(client, email="reader-owner@example.ga")
    attacker_access, _ = create_user_and_token(client, email="reader-attacker@example.ga")
    document = create_readable_document(slug="reader-v1-owner-session")
    session_response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
        **auth_headers(owner_access),
    )

    response = client.get(
        f"/api/v1/reader/sessions/{session_response.json()['session_key']}/pages/1/",
        **auth_headers(attacker_access),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"


@pytest.mark.django_db
def test_reader_page_access_is_denied_after_entitlement_revocation():
    client = APIClient()
    access, user = create_user_and_token(client)
    document = create_readable_document(
        slug="reader-v1-revoked-entitlement",
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    entitlement = Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=document.entitlement_scope_id,
        starts_at=timezone.now() - timezone.timedelta(minutes=5),
        ends_at=timezone.now() + timezone.timedelta(minutes=30),
    )
    session_response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
        **auth_headers(access),
    )
    entitlement.revoked_at = timezone.now()
    entitlement.save(update_fields=["revoked_at", "updated_at"])

    response = client.get(
        f"/api/v1/reader/sessions/{session_response.json()['session_key']}/pages/1/",
        **auth_headers(access),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "entitlement_required"


def test_openapi_schema_documents_reader_endpoints():
    paths = SchemaGenerator().get_schema(request=None, public=True)["paths"]

    expected_operations = {
        "/api/v1/reader/sessions/": {"post": {"201", "400", "401", "403", "404"}},
        "/api/v1/reader/sessions/{session_key}/pages/{page_number}/": {
            "get": {"200", "403", "404"}
        },
        "/api/v1/reader/sessions/{session_key}/": {"delete": {"204", "403"}},
    }

    for path, operations in expected_operations.items():
        for method, response_codes in operations.items():
            operation = paths[path][method]
            assert response_codes <= set(operation["responses"])
            if method == "post":
                assert "requestBody" in operation
