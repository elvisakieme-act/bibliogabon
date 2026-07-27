import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from accounts.models import Entitlement
from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_processing.services import attach_extracted_text, create_page_records
from document_reader.models import ReaderSession
from document_reader.services import start_reader_session


def create_user(email="reader-api@example.ga"):
    return get_user_model().objects.create_user(email=email, password="pass")


def create_document(slug="reader-api-document", access_model=Document.AccessModel.FREE):
    domain = AcademicDomain.objects.create(name=f"Reader API {slug}", slug=f"reader-api-{slug}")
    return Document.objects.create(
        title=f"Reader API {slug}",
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )


def create_readable_document(slug="reader-api-document", access_model=Document.AccessModel.FREE):
    document = create_document(slug=slug, access_model=access_model)
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
    attach_extracted_text(page=page, text="Texte API lisible.", language_code="fr")
    return document, version, page


@pytest.mark.django_db
def test_start_reader_session_api_requires_authentication(client):
    document, _, _ = create_readable_document()

    response = client.post(f"/reader/documents/{document.pk}/sessions/")

    assert response.status_code == 401
    assert response.json() == {"error": "authentication_required"}


@pytest.mark.django_db
def test_reader_post_without_csrf_returns_json_403():
    document, _, _ = create_readable_document()
    csrf_client = Client(enforce_csrf_checks=True)

    response = csrf_client.post(f"/reader/documents/{document.pk}/sessions/")

    assert response.status_code == 403
    assert response["Content-Type"].startswith("application/json")
    assert response.json() == {"error": "csrf_failed"}


@pytest.mark.django_db
def test_start_reader_session_api_creates_reader_session(client):
    user = create_user()
    document, version, _ = create_readable_document()
    client.force_login(user)

    response = client.post(f"/reader/documents/{document.pk}/sessions/")

    assert response.status_code == 201
    payload = response.json()
    assert payload["document_id"] == document.pk
    assert payload["version_id"] == version.pk
    assert ReaderSession.objects.filter(session_key=payload["session_key"], user=user).exists()


@pytest.mark.django_db
def test_reader_page_api_returns_safe_payload(client):
    user = create_user()
    document, _, _ = create_readable_document()
    session = start_reader_session(user=user, document=document)
    client.force_login(user)

    response = client.get(f"/reader/sessions/{session.session_key}/pages/1/")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "session_key",
        "document_id",
        "version_id",
        "page_number",
        "page_count",
        "language_code",
        "text",
    }
    assert payload["text"] == "Texte API lisible."


@pytest.mark.django_db
def test_reader_page_api_rejects_session_key_reuse_by_another_user(client):
    owner = create_user(email="owner@example.ga")
    other = create_user(email="other@example.ga")
    document, _, _ = create_readable_document()
    session = start_reader_session(user=owner, document=document)
    client.force_login(other)

    response = client.get(f"/reader/sessions/{session.session_key}/pages/1/")

    assert response.status_code == 403
    assert response.json() == {"error": "access_denied"}


@pytest.mark.django_db
def test_reader_page_api_rechecks_revoked_entitlement(client):
    user = create_user()
    document, _, _ = create_readable_document(access_model=Document.AccessModel.SUBSCRIPTION)
    entitlement = Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=document.entitlement_scope_id,
        starts_at=timezone.now() - timezone.timedelta(minutes=5),
        ends_at=timezone.now() + timezone.timedelta(minutes=5),
    )
    session = start_reader_session(user=user, document=document)
    entitlement.revoked_at = timezone.now()
    entitlement.save(update_fields=["revoked_at", "updated_at"])
    client.force_login(user)

    response = client.get(f"/reader/sessions/{session.session_key}/pages/1/")

    assert response.status_code == 403
    assert response.json() == {"error": "access_denied"}


@pytest.mark.django_db
def test_end_reader_session_api_marks_session_ended(client):
    user = create_user()
    document, _, _ = create_readable_document()
    session = start_reader_session(user=user, document=document)
    client.force_login(user)

    response = client.post(f"/reader/sessions/{session.session_key}/end/")

    session.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["status"] == ReaderSession.Status.ENDED
    assert session.status == ReaderSession.Status.ENDED
