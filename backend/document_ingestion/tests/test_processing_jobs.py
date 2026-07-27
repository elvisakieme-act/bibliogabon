import pytest
from django.core.exceptions import ValidationError

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob
from document_ingestion.services import enqueue_processing_job


def create_version_and_asset():
    domain = AcademicDomain.objects.create(name="Medecine numerique", slug="medecine-numerique")
    document = Document.objects.create(
        title="Sante numerique",
        slug="sante-numerique",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.PRIVATE,
    )
    version = DocumentVersion.objects.create(document=document, version_label="v1")
    asset = DocumentAsset.objects.create(
        version=version,
        asset_type=DocumentAsset.AssetType.SOURCE_PDF,
        storage_bucket="bibliogabon-private-documents",
        storage_key="documents/1/versions/v1/abcd1234/source.pdf",
        mime_type="application/pdf",
        byte_size=4096,
        checksum_sha256="d" * 64,
    )
    return version, asset


@pytest.mark.django_db
def test_enqueue_processing_job_is_idempotent_by_key():
    version, asset = create_version_and_asset()

    first = enqueue_processing_job(
        version=version,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key="document-1-v1-ingest",
        source_asset=asset,
    )
    second = enqueue_processing_job(
        version=version,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key="document-1-v1-ingest",
        source_asset=asset,
    )

    assert first.pk == second.pk
    assert ProcessingJob.objects.count() == 1
    assert first.status == ProcessingJob.Status.QUEUED


@pytest.mark.django_db
def test_enqueue_processing_job_rejects_idempotency_conflict():
    version, asset = create_version_and_asset()
    enqueue_processing_job(
        version=version,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key="document-1-v1-conflict",
        source_asset=asset,
    )

    with pytest.raises(ValueError):
        enqueue_processing_job(
            version=version,
            job_type=ProcessingJob.JobType.EXTRACT_METADATA,
            idempotency_key="document-1-v1-conflict",
            source_asset=asset,
        )


@pytest.mark.django_db
def test_processing_job_save_rejects_source_asset_from_other_version():
    version, asset = create_version_and_asset()
    other_version = DocumentVersion.objects.create(document=version.document, version_label="v2")
    job = ProcessingJob(
        version=other_version,
        source_asset=asset,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key="document-1-v2-mismatch",
    )

    with pytest.raises(ValidationError):
        job.save()


@pytest.mark.django_db
def test_processing_job_state_transitions_record_timestamps_and_errors():
    version, asset = create_version_and_asset()
    completed_job = enqueue_processing_job(
        version=version,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key="document-1-v1-complete",
        source_asset=asset,
    )

    completed_job.mark_started()
    assert completed_job.status == ProcessingJob.Status.RUNNING
    assert completed_job.started_at is not None

    completed_job.mark_completed(output_asset_ids=[12, 13])
    assert completed_job.status == ProcessingJob.Status.SUCCEEDED
    assert completed_job.output_asset_ids == [12, 13]
    assert completed_job.completed_at is not None

    failed_job = enqueue_processing_job(
        version=version,
        job_type=ProcessingJob.JobType.INGEST_SOURCE,
        idempotency_key="document-1-v1-fail",
        source_asset=asset,
    )
    failed_job.mark_started()
    failed_job.mark_failed(error_code="parse_error", message="Unsupported file")
    assert failed_job.status == ProcessingJob.Status.FAILED
    assert failed_job.retry_count == 1
    assert failed_job.error_code == "parse_error"
    assert failed_job.error_message == "Unsupported file"
    assert failed_job.failed_at is not None
