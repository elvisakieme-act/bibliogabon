import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob
from document_ingestion.services import register_private_upload


def create_document():
    domain = AcademicDomain.objects.create(name="Archives academiques", slug="archives-academiques")
    return Document.objects.create(
        title="Archives numeriques UOB",
        slug="archives-numeriques-uob",
        academic_domain=domain,
        category=Document.Category.INSTITUTIONAL_FUND,
        access_model=Document.AccessModel.PRIVATE,
    )


@pytest.mark.django_db
def test_register_private_upload_creates_version_asset_and_job(settings):
    settings.DOCUMENT_STORAGE_BUCKET = "bibliogabon-private-documents"
    User = get_user_model()
    user = User.objects.create_user(email="staff@example.ga", password="pass")
    document = create_document()

    asset = register_private_upload(
        document=document,
        storage_key="documents/1/versions/v1/abcdef12/source.pdf",
        original_filename="source.pdf",
        mime_type="application/pdf",
        byte_size=8192,
        checksum_sha256="e" * 64,
        uploaded_by=user,
        version_label="v1",
    )

    version = asset.version
    job = ProcessingJob.objects.get(version=version)

    assert version.document == document
    assert version.version_label == "v1"
    assert version.uploaded_by == user
    assert asset.asset_type == DocumentAsset.AssetType.SOURCE_PDF
    assert asset.storage_bucket == "bibliogabon-private-documents"
    assert job.status == ProcessingJob.Status.QUEUED
    assert job.source_asset == asset


@pytest.mark.django_db
def test_register_private_upload_is_idempotent_for_same_version_and_checksum(settings):
    settings.DOCUMENT_STORAGE_BUCKET = "bibliogabon-private-documents"
    document = create_document()

    first = register_private_upload(
        document=document,
        storage_key="documents/1/versions/v1/abcdef12/source.pdf",
        original_filename="source.pdf",
        mime_type="application/pdf",
        byte_size=8192,
        checksum_sha256="f" * 64,
        version_label="v1",
    )
    second = register_private_upload(
        document=document,
        storage_key="documents/1/versions/v1/abcdef12/source.pdf",
        original_filename="source.pdf",
        mime_type="application/pdf",
        byte_size=8192,
        checksum_sha256="f" * 64,
        version_label="v1",
    )

    assert first.pk == second.pk
    assert DocumentVersion.objects.count() == 1
    assert DocumentAsset.objects.count() == 1
    assert ProcessingJob.objects.count() == 1


@pytest.mark.django_db
def test_register_private_upload_rejects_conflicting_asset_metadata(settings):
    settings.DOCUMENT_STORAGE_BUCKET = "bibliogabon-private-documents"
    document = create_document()
    register_private_upload(
        document=document,
        storage_key="documents/1/versions/v1/abcdef12/source.pdf",
        original_filename="source.pdf",
        mime_type="application/pdf",
        byte_size=8192,
        checksum_sha256="b" * 64,
        version_label="v1",
    )

    with pytest.raises(ValueError):
        register_private_upload(
            document=document,
            storage_key="documents/1/versions/v1/abcdef12/source.pdf",
            original_filename="source.pdf",
            mime_type="application/pdf",
            byte_size=4096,
            checksum_sha256="b" * 64,
            version_label="v1",
        )


@pytest.mark.django_db
def test_register_private_upload_is_atomic_when_job_creation_fails(settings, monkeypatch):
    settings.DOCUMENT_STORAGE_BUCKET = "bibliogabon-private-documents"

    def fail_to_enqueue(*args, **kwargs):
        raise IntegrityError("job failed")

    monkeypatch.setattr("document_ingestion.services.enqueue_processing_job", fail_to_enqueue)

    with pytest.raises(IntegrityError):
        register_private_upload(
            document=create_document(),
            storage_key="documents/1/versions/v1/abcdef12/source.pdf",
            original_filename="source.pdf",
            mime_type="application/pdf",
            byte_size=8192,
            checksum_sha256="c" * 64,
            version_label="v1",
        )

    assert DocumentVersion.objects.count() == 0
    assert DocumentAsset.objects.count() == 0


@pytest.mark.parametrize(
    "storage_key",
    [
        "http://example.com/source.pdf",
        "https://example.com/source.pdf",
        "file:///tmp/source.pdf",
    ],
)
@pytest.mark.django_db
def test_register_private_upload_rejects_public_storage_reference(storage_key):
    with pytest.raises(ValueError):
        register_private_upload(
            document=create_document(),
            storage_key=storage_key,
            original_filename="source.pdf",
            mime_type="application/pdf",
            byte_size=8192,
            checksum_sha256="a" * 64,
            version_label="v1",
        )
