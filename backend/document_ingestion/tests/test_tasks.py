from __future__ import annotations

import io

import pytest
from celery.exceptions import Retry
from django.conf import settings as django_settings

from catalog.models import AcademicDomain, Document
from document_ingestion import tasks
from document_ingestion.blob_storage import save_stream
from document_ingestion.models import ProcessingJob
from document_ingestion.services import register_private_upload
from document_ingestion.storage import build_private_storage_key
from document_ingestion.tasks import ingest_source_document
from document_processing.models import DocumentPage


def build_pdf(pages: int = 2) -> bytes:
    import pymupdf

    document = pymupdf.open()
    for number in range(1, pages + 1):
        page = document.new_page()
        page.insert_text((72, 72), f"Page {number} de test d'ingestion")
    return document.tobytes()


def create_queued_job(*, slug: str = "tache-ingestion", pages: int = 2) -> ProcessingJob:
    """Prépare un job prêt à traiter, sans le traiter : c'est exactement
    l'état qu'un worker Celery trouvera en sortie de file."""
    domain, _ = AcademicDomain.objects.get_or_create(name="Reseaux", slug="reseaux")
    document = Document.objects.create(
        title="Document de tache",
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )
    payload = build_pdf(pages)
    import hashlib

    checksum = hashlib.sha256(payload).hexdigest()
    storage_key = build_private_storage_key(
        document=document,
        version_label="v1",
        original_filename="source.pdf",
        checksum_sha256=checksum,
    )
    save_stream(storage_key, io.BytesIO(payload))
    register_private_upload(
        document=document,
        storage_key=storage_key,
        original_filename="source.pdf",
        mime_type="application/pdf",
        byte_size=len(payload),
        checksum_sha256=checksum,
        version_label="v1",
    )
    return ProcessingJob.objects.get(
        idempotency_key=f"ingest:{document.pk}:v1:{checksum}"
    )


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    return tmp_path


def test_the_suite_runs_without_a_broker():
    assert django_settings.CELERY_TASK_ALWAYS_EAGER is True


def test_celery_app_reads_its_configuration_from_django_settings():
    from config.celery import celery_app

    assert celery_app.conf.task_always_eager is django_settings.CELERY_TASK_ALWAYS_EAGER


@pytest.mark.django_db
def test_task_processes_the_job_and_returns_the_version(local_storage):
    job = create_queued_job(pages=3)

    version_id = ingest_source_document.apply(args=[job.pk]).get()

    job.refresh_from_db()
    assert job.status == ProcessingJob.Status.SUCCEEDED
    assert version_id == job.version_id
    job.version.refresh_from_db()
    assert job.version.page_count == 3
    assert DocumentPage.objects.filter(version=job.version).count() == 3


@pytest.mark.django_db
def test_task_records_the_celery_task_id(local_storage):
    job = create_queued_job()

    ingest_source_document.apply(args=[job.pk]).get()

    job.refresh_from_db()
    assert job.celery_task_id


@pytest.mark.django_db
def test_replaying_a_succeeded_job_changes_nothing(local_storage):
    job = create_queued_job(pages=2)
    ingest_source_document.apply(args=[job.pk]).get()
    job.refresh_from_db()
    completed_at = job.completed_at

    version_id = ingest_source_document.apply(args=[job.pk]).get()

    job.refresh_from_db()
    assert version_id == job.version_id
    assert job.completed_at == completed_at, "le job a été retraité"
    assert DocumentPage.objects.filter(version=job.version).count() == 2


@pytest.mark.django_db
def test_failure_propagates_the_original_error_when_running_inline(
    local_storage, monkeypatch
):
    job = create_queued_job()

    def explode(job):
        job.mark_failed(error_code="ingest_failed", message="pdf illisible")
        raise ValueError("pdf illisible")

    monkeypatch.setattr(tasks, "process_ingest_job", explode)

    with pytest.raises(ValueError):
        ingest_source_document.apply(args=[job.pk]).get()

    job.refresh_from_db()
    assert job.status == ProcessingJob.Status.FAILED
    assert job.error_code == "ingest_failed"
    assert job.error_message == "pdf illisible"


@pytest.mark.django_db
@pytest.mark.parametrize("attempts", [0, 2, 3])
def test_retry_count_reflects_the_celery_attempt_number(
    local_storage, monkeypatch, attempts
):
    job = create_queued_job(slug=f"tache-retry-{attempts}")

    def explode(job):
        job.mark_failed(error_code="ingest_failed", message="echec")
        raise ValueError("echec")

    monkeypatch.setattr(tasks, "process_ingest_job", explode)

    with pytest.raises(ValueError):
        ingest_source_document.apply(args=[job.pk], retries=attempts).get()

    job.refresh_from_db()
    assert job.retry_count == attempts


@pytest.mark.django_db
def test_mark_failed_no_longer_guesses_the_retry_count(local_storage):
    job = create_queued_job()

    job.mark_failed(error_code="parse_error", message="illisible")

    job.refresh_from_db()
    assert job.status == ProcessingJob.Status.FAILED
    assert job.retry_count == 0, "le compteur appartient à ce qui réessaie"


@pytest.mark.django_db
def test_a_retryable_attempt_is_recorded_as_retrying(local_storage):
    job = create_queued_job()

    job.mark_retrying(error_code="ingest_failed", message="echec", retry_count=1)

    job.refresh_from_db()
    assert job.status == ProcessingJob.Status.RETRYING
    assert job.retry_count == 1
    assert job.error_code == "ingest_failed"


@pytest.mark.django_db
def test_task_schedules_a_retry_when_a_broker_is_in_play(local_storage, monkeypatch):
    job = create_queued_job()

    def explode(job):
        job.mark_failed(error_code="ingest_failed", message="echec")
        raise ValueError("echec")

    monkeypatch.setattr(tasks, "process_ingest_job", explode)
    # Hors mode inline, un echec restant sous le plafond doit reprogrammer la
    # tache plutot que d'abandonner.
    monkeypatch.setattr(tasks, "runs_inline", lambda: False)

    with pytest.raises(Retry):
        ingest_source_document.apply(args=[job.pk]).get()

    job.refresh_from_db()
    assert job.status == ProcessingJob.Status.RETRYING
