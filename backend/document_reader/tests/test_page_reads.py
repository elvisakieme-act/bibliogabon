import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Entitlement
from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_processing.services import attach_extracted_text, create_page_records
from document_reader.exceptions import ReaderAccessDenied, ReaderPageUnavailable, ReaderSessionInactive
from document_reader.models import PageAccessLog, ReaderSession
from document_reader.services import get_reader_page, start_reader_session


def create_user(email="reader-page@example.ga"):
    return get_user_model().objects.create_user(email=email, password="pass")


def create_document(
    slug="reader-page-document",
    access_model=Document.AccessModel.FREE,
    publication_status=Document.PublicationStatus.PUBLISHED,
):
    domain = AcademicDomain.objects.create(name=f"Reader Page {slug}", slug=f"reader-page-{slug}")
    return Document.objects.create(
        title=f"Reader Page {slug}",
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=publication_status,
    )


def create_processed_version(document, page_count=1):
    return DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=page_count,
    )


def create_processed_page(version, page_number=1, text="Texte lisible."):
    page = create_page_records(version=version, page_count=version.page_count)[page_number - 1]
    page.status = DocumentPage.Status.PROCESSED
    page.save(update_fields=["status", "updated_at"])
    attach_extracted_text(page=page, text=text, language_code="fr")
    return page


def create_free_session_with_page():
    user = create_user()
    document = create_document()
    version = create_processed_version(document)
    page = create_processed_page(version)
    session = start_reader_session(
        user=user,
        document=document,
        client_ip="196.223.12.10",
        user_agent="BiblioGABON test client",
    )
    return session, page


@pytest.mark.django_db
def test_get_reader_page_returns_safe_payload_and_logs_success():
    session, page = create_free_session_with_page()

    payload = get_reader_page(session=session, page_number=1)

    assert payload == {
        "session_key": str(session.session_key),
        "document_id": session.document_id,
        "version_id": session.version_id,
        "page_number": 1,
        "page_count": 1,
        "language_code": "fr",
        "text": "Texte lisible.",
    }
    log = PageAccessLog.objects.get()
    assert log.session == session
    assert log.page == page
    assert log.user == session.user
    assert log.document == session.document


@pytest.mark.django_db
def test_get_reader_page_rejects_expired_session():
    session, _ = create_free_session_with_page()
    at = session.expires_at

    with pytest.raises(ReaderSessionInactive):
        get_reader_page(session=session, page_number=1, at=at)

    assert PageAccessLog.objects.count() == 0


@pytest.mark.django_db
def test_get_reader_page_rejects_ended_session():
    session, _ = create_free_session_with_page()
    session.end()

    with pytest.raises(ReaderSessionInactive):
        get_reader_page(session=session, page_number=1)

    assert PageAccessLog.objects.count() == 0


@pytest.mark.django_db
def test_get_reader_page_rechecks_expired_entitlement_after_session_start():
    user = create_user()
    document = create_document(access_model=Document.AccessModel.SUBSCRIPTION)
    version = create_processed_version(document)
    create_processed_page(version)
    started_at = timezone.now()
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=document.entitlement_scope_id,
        starts_at=started_at - timezone.timedelta(minutes=5),
        ends_at=started_at + timezone.timedelta(minutes=5),
    )
    session = start_reader_session(user=user, document=document, at=started_at)

    with pytest.raises(ReaderAccessDenied):
        get_reader_page(session=session, page_number=1, at=started_at + timezone.timedelta(minutes=6))

    assert PageAccessLog.objects.count() == 0


@pytest.mark.parametrize(
    ("publication_status", "access_model"),
    [
        (Document.PublicationStatus.WITHDRAWN, Document.AccessModel.FREE),
        (Document.PublicationStatus.SUSPENDED, Document.AccessModel.FREE),
        (Document.PublicationStatus.PUBLISHED, Document.AccessModel.PRIVATE),
    ],
)
@pytest.mark.django_db
def test_get_reader_page_rechecks_document_readability_after_session_start(publication_status, access_model):
    session, _ = create_free_session_with_page()
    session.document.publication_status = publication_status
    session.document.access_model = access_model
    session.document.save(update_fields=["publication_status", "access_model", "updated_at"])

    with pytest.raises(ReaderAccessDenied):
        get_reader_page(session=session, page_number=1)

    assert PageAccessLog.objects.count() == 0


@pytest.mark.parametrize("page_number", [0, 2])
@pytest.mark.django_db
def test_get_reader_page_rejects_missing_or_out_of_bounds_page(page_number):
    session, _ = create_free_session_with_page()

    with pytest.raises(ReaderPageUnavailable):
        get_reader_page(session=session, page_number=page_number)

    assert PageAccessLog.objects.count() == 0


@pytest.mark.django_db
def test_get_reader_page_rejects_unprocessed_page():
    session, page = create_free_session_with_page()
    page.status = DocumentPage.Status.PENDING
    page.save(update_fields=["status", "updated_at"])

    with pytest.raises(ReaderPageUnavailable):
        get_reader_page(session=session, page_number=1)

    assert PageAccessLog.objects.count() == 0


@pytest.mark.django_db
def test_get_reader_page_rejects_page_without_extracted_text():
    session, page = create_free_session_with_page()
    page.extracted_text.delete()

    with pytest.raises(ReaderPageUnavailable):
        get_reader_page(session=session, page_number=1)

    assert PageAccessLog.objects.count() == 0
