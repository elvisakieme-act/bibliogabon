import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Entitlement, Organization, OrganizationMembership
from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_reader.exceptions import ReaderAccessDenied
from document_reader.models import PageAccessLog, ReaderSession
from document_reader.services import end_reader_session, start_reader_session


def create_document(
    slug="reader-document",
    access_model=Document.AccessModel.FREE,
    publication_status=Document.PublicationStatus.PUBLISHED,
):
    domain = AcademicDomain.objects.create(name=f"Reader {slug}", slug=f"reader-{slug}")
    return Document.objects.create(
        title=f"Reader {slug}",
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=publication_status,
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


def create_processed_version(document):
    return DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=1,
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
def test_reader_session_save_rejects_missing_expiry_with_validation_error():
    user = create_user()
    document = create_document()
    version = DocumentVersion.objects.create(document=document, version_label="v1")
    session = ReaderSession(
        user=user,
        document=document,
        version=version,
        started_at=timezone.now(),
        expires_at=None,
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


@pytest.mark.django_db
def test_start_reader_session_allows_published_free_document_without_entitlement(settings):
    settings.READER_SESSION_TTL_MINUTES = 30
    user = create_user()
    document = create_document()
    version = create_processed_version(document)
    started_at = timezone.now()

    session = start_reader_session(
        user=user,
        document=document,
        client_ip="196.223.12.10",
        user_agent="BiblioGABON test client",
        at=started_at,
    )

    assert session.user == user
    assert session.document == document
    assert session.version == version
    assert session.expires_at == started_at + timezone.timedelta(minutes=30)


@pytest.mark.django_db
def test_start_reader_session_rejects_anonymous_user():
    document = create_document()
    create_processed_version(document)

    with pytest.raises(ReaderAccessDenied):
        start_reader_session(user=AnonymousUser(), document=document)


@pytest.mark.django_db
def test_start_reader_session_rejects_unpublished_document():
    user = create_user()
    document = create_document(publication_status=Document.PublicationStatus.DRAFT)
    create_processed_version(document)

    with pytest.raises(ReaderAccessDenied):
        start_reader_session(user=user, document=document)


@pytest.mark.django_db
def test_start_reader_session_rejects_private_document_even_with_entitlement():
    user = create_user()
    document = create_document(access_model=Document.AccessModel.PRIVATE)
    create_processed_version(document)
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.ADMIN_GRANT,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=document.entitlement_scope_id,
    )

    with pytest.raises(ReaderAccessDenied):
        start_reader_session(user=user, document=document)


@pytest.mark.parametrize(
    "access_model",
    [
        Document.AccessModel.SUBSCRIPTION,
        Document.AccessModel.INSTITUTION_ONLY,
        Document.AccessModel.SPONSORED,
        Document.AccessModel.RESTRICTED,
    ],
)
@pytest.mark.django_db
def test_start_reader_session_rejects_restricted_document_without_read_entitlement(access_model):
    user = create_user()
    document = create_document(access_model=access_model)
    create_processed_version(document)

    with pytest.raises(ReaderAccessDenied):
        start_reader_session(user=user, document=document)


@pytest.mark.parametrize(
    "access_model",
    [
        Document.AccessModel.SUBSCRIPTION,
        Document.AccessModel.INSTITUTION_ONLY,
        Document.AccessModel.SPONSORED,
        Document.AccessModel.RESTRICTED,
    ],
)
@pytest.mark.django_db
def test_start_reader_session_allows_restricted_document_with_document_entitlement(access_model):
    user = create_user()
    document = create_document(access_model=access_model)
    create_processed_version(document)
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=document.entitlement_scope_id,
    )

    session = start_reader_session(user=user, document=document)

    assert session.status == ReaderSession.Status.ACTIVE


@pytest.mark.django_db
def test_start_reader_session_allows_restricted_document_with_global_organization_entitlement():
    user = create_user()
    organization = Organization.objects.create(name="Ecole nationale", slug="ecole-nationale")
    OrganizationMembership.objects.create(organization=organization, user=user)
    document = create_document(access_model=Document.AccessModel.SPONSORED)
    create_processed_version(document)
    Entitlement.objects.create(
        organization=organization,
        source=Entitlement.Source.ORGANIZATION_QUOTA,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
    )

    session = start_reader_session(user=user, document=document)

    assert session.user == user
    assert session.document == document


@pytest.mark.django_db
def test_start_reader_session_allows_restricted_document_with_domain_entitlement():
    user = create_user()
    document = create_document(access_model=Document.AccessModel.RESTRICTED)
    create_processed_version(document)
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOMAIN,
        scope_id=str(document.academic_domain_id),
    )

    session = start_reader_session(user=user, document=document)

    assert session.document == document


@pytest.mark.django_db
def test_start_reader_session_rejects_document_without_processed_current_version():
    user = create_user()
    document = create_document()
    DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSING,
        is_current=True,
        page_count=1,
    )

    with pytest.raises(ReaderAccessDenied):
        start_reader_session(user=user, document=document)


@pytest.mark.django_db
def test_end_reader_session_service_records_session_end():
    session = create_session()
    ended_at = session.started_at + timezone.timedelta(minutes=10)

    ended = end_reader_session(session=session, at=ended_at)

    assert ended.status == ReaderSession.Status.ENDED
    assert ended.ended_at == ended_at
