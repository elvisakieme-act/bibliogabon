import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_reader.models import PageAccessLog, ReaderSession


def create_document(slug="reader-document", access_model=Document.AccessModel.FREE):
    domain = AcademicDomain.objects.create(name=f"Reader {slug}", slug=f"reader-{slug}")
    return Document.objects.create(
        title=f"Reader {slug}",
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )


def create_user(email="reader@example.ga"):
    return get_user_model().objects.create_user(email=email, password="pass")


def create_session():
    user = create_user()
    document = create_document()
    version = DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
    )
    started_at = timezone.now()
    return ReaderSession.objects.create(
        user=user,
        document=document,
        version=version,
        started_at=started_at,
        expires_at=started_at + timezone.timedelta(minutes=120),
        client_ip="196.223.12.10",
        user_agent="BiblioGABON test client",
    )


@pytest.mark.django_db
def test_reader_session_stores_user_document_version_expiry_and_client_metadata():
    session = create_session()

    assert session.status == ReaderSession.Status.ACTIVE
    assert session.session_key is not None
    assert session.client_ip == "196.223.12.10"
    assert session.user_agent == "BiblioGABON test client"
    assert session.expires_at > session.started_at


@pytest.mark.django_db
def test_reader_session_save_rejects_version_from_other_document():
    user = create_user()
    document = create_document(slug="document-a")
    other_document = create_document(slug="document-b")
    other_version = DocumentVersion.objects.create(document=other_document, version_label="v1")
    started_at = timezone.now()
    session = ReaderSession(
        user=user,
        document=document,
        version=other_version,
        started_at=started_at,
        expires_at=started_at + timezone.timedelta(minutes=120),
    )

    with pytest.raises(ValidationError):
        session.save()


@pytest.mark.django_db
def test_reader_session_is_active_only_before_expiry_and_before_end():
    session = create_session()

    assert session.is_active_at(session.started_at + timezone.timedelta(minutes=30)) is True
    assert session.is_active_at(session.expires_at) is False

    session.end(at=session.started_at + timezone.timedelta(minutes=40))
    assert session.is_active_at(session.started_at + timezone.timedelta(minutes=41)) is False


@pytest.mark.django_db
def test_reader_session_end_records_timestamp_and_status():
    session = create_session()
    ended_at = session.started_at + timezone.timedelta(minutes=15)

    session.end(at=ended_at)

    assert session.status == ReaderSession.Status.ENDED
    assert session.ended_at == ended_at
    assert session.last_seen_at == ended_at


@pytest.mark.django_db
def test_page_access_log_stores_session_page_context():
    session = create_session()
    page = DocumentPage.objects.create(
        version=session.version,
        page_number=1,
        status=DocumentPage.Status.PROCESSED,
    )

    access_log = PageAccessLog.objects.create(
        session=session,
        page=page,
        user=session.user,
        document=session.document,
        page_number=1,
        client_ip=session.client_ip,
        user_agent=session.user_agent,
    )

    assert access_log.user == session.user
    assert access_log.document == session.document
    assert access_log.page_number == 1
    assert access_log.client_ip == "196.223.12.10"


@pytest.mark.django_db
def test_page_access_log_save_rejects_page_from_other_session_version():
    session = create_session()
    other_version = DocumentVersion.objects.create(document=session.document, version_label="v2")
    page = DocumentPage.objects.create(version=other_version, page_number=1)

    access_log = PageAccessLog(
        session=session,
        page=page,
        user=session.user,
        document=session.document,
        page_number=1,
    )

    with pytest.raises(ValidationError):
        access_log.save()
