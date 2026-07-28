from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Organization, OrganizationMembership
from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_reader.models import PageAccessLog, ReaderSession


def create_user(email="analytics-reader@example.ga"):
    return get_user_model().objects.create_user(email=email, password="pass")


def create_organization(slug="analytics-org"):
    return Organization.objects.create(name=f"Organization {slug}", slug=slug)


def create_active_membership(user, organization, *, starts_at=None, ends_at=None):
    return OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        status=OrganizationMembership.Status.ACTIVE,
        starts_at=starts_at or timezone.now() - timezone.timedelta(days=1),
        ends_at=ends_at,
    )


def create_document(slug="analytics-document", access_model=Document.AccessModel.FREE):
    domain = AcademicDomain.objects.create(name=f"Domain {slug}", slug=f"domain-{slug}")
    return Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )


def create_reader_activity(*, user, document, started_at, page_views=1):
    version = DocumentVersion.objects.create(
        document=document,
        version_label=f"v-{document.pk}-{started_at.strftime('%Y%m%d%H%M%S')}",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=max(page_views, 1),
    )
    session = ReaderSession.objects.create(
        user=user,
        document=document,
        version=version,
        started_at=started_at,
        expires_at=started_at + timezone.timedelta(hours=2),
        last_seen_at=started_at,
        client_ip="196.223.12.10",
        user_agent="BiblioGABON test client",
    )
    for page_number in range(1, page_views + 1):
        page = DocumentPage.objects.create(
            version=version,
            page_number=page_number,
            status=DocumentPage.Status.PROCESSED,
        )
        PageAccessLog.objects.create(
            session=session,
            page=page,
            user=user,
            document=document,
            page_number=page_number,
            accessed_at=started_at + timezone.timedelta(minutes=page_number),
            client_ip=session.client_ip,
            user_agent=session.user_agent,
        )
    return session
