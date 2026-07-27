import pytest
from django.core.exceptions import ValidationError

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion, ProcessingJob
from document_processing.models import DocumentPage
from document_processing.services import create_page_records


def create_document(slug="pages-document"):
    domain = AcademicDomain.objects.create(name=f"Sciences {slug}", slug=f"sciences-{slug}")
    return Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.PRIVATE,
    )


def create_version(version_label="v1"):
    return DocumentVersion.objects.create(
        document=create_document(slug=f"pages-document-{version_label}"),
        version_label=version_label,
    )


@pytest.mark.django_db
def test_create_page_records_creates_ordered_pages_and_updates_version_page_count():
    version = create_version()

    pages = create_page_records(version=version, page_count=3)

    version.refresh_from_db()
    assert [page.page_number for page in pages] == [1, 2, 3]
    assert [page.status for page in pages] == [
        DocumentPage.Status.PENDING,
        DocumentPage.Status.PENDING,
        DocumentPage.Status.PENDING,
    ]
    assert version.page_count == 3


@pytest.mark.django_db
def test_create_page_records_is_idempotent_for_same_page_count():
    version = create_version()
    first = create_page_records(version=version, page_count=2)

    second = create_page_records(version=version, page_count=2)

    assert [page.pk for page in second] == [page.pk for page in first]
    assert DocumentPage.objects.filter(version=version).count() == 2


@pytest.mark.django_db
def test_create_page_records_rejects_changed_page_count_retry():
    version = create_version()
    create_page_records(version=version, page_count=2)

    with pytest.raises(ValueError):
        create_page_records(version=version, page_count=3)

    assert list(DocumentPage.objects.filter(version=version).values_list("page_number", flat=True)) == [1, 2]


@pytest.mark.parametrize("page_count", [0, -1])
@pytest.mark.django_db
def test_create_page_records_rejects_non_positive_page_count(page_count):
    with pytest.raises(ValueError):
        create_page_records(version=create_version(version_label=f"v{abs(page_count)}"), page_count=page_count)


@pytest.mark.django_db
def test_document_page_is_unique_per_version_and_page_number():
    version = create_version()
    DocumentPage.objects.create(version=version, page_number=1)

    with pytest.raises(ValidationError):
        DocumentPage.objects.create(version=version, page_number=1)


@pytest.mark.django_db
def test_document_page_save_rejects_processing_job_from_other_version():
    version = create_version()
    other_version = DocumentVersion.objects.create(document=version.document, version_label="v2")
    other_job = ProcessingJob.objects.create(
        version=other_version,
        job_type=ProcessingJob.JobType.GENERATE_DERIVATIVES,
        idempotency_key="other-version-page-job",
    )
    page = DocumentPage(version=version, page_number=1, created_by_job=other_job)

    with pytest.raises(ValidationError):
        page.save()
