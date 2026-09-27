from __future__ import annotations

from pathlib import Path

import pytest
from django.urls import reverse

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentAsset, ProcessingJob
from document_ingestion.pipeline import ingest_document_file
from document_ingestion.tests.ingestion_helpers import tesseract_marker
from document_processing.models import DocumentPage, ExtractedText, SearchIndexRecord
from search_discovery.services import search_documents

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-3-pages.pdf"

needs_tesseract = tesseract_marker()


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    settings.DOCUMENT_PAGE_IMAGE_WIDTH = 480
    return tmp_path


@pytest.fixture
def ingested(local_storage, db):
    domain = AcademicDomain.objects.create(name="Reseaux", slug="reseaux-e2e")
    document = Document.objects.create(
        title="Comprendre la 4G",
        slug="comprendre-la-4g",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )
    with FIXTURE.open("rb") as handle:
        return ingest_document_file(
            document=document, fileobj=handle, original_filename="sample.pdf"
        )


def test_the_version_is_processed_and_current(ingested):
    assert ingested.status == "processed"
    assert ingested.is_current is True
    assert ingested.page_count == 3
    assert ingested.detected_format == "pdf"


def test_the_job_succeeded(ingested):
    job = ProcessingJob.objects.get(version=ingested)

    assert job.status == ProcessingJob.Status.SUCCEEDED
    assert job.completed_at is not None
    assert job.error_code == ""


def test_every_page_has_normalised_text(ingested):
    texts = ExtractedText.objects.filter(page__version=ingested)

    assert texts.count() == 3
    for text in texts:
        assert not any(
            ord(character) < 32 and character not in "\n\t" for character in text.text
        )


@needs_tesseract
def test_the_image_only_page_went_through_ocr(ingested):
    text = ExtractedText.objects.get(page__version=ingested, page__page_number=3)

    assert text.extraction_method == ExtractedText.ExtractionMethod.OCR
    assert "NUMERISE" in text.text.upper()
    assert text.confidence is not None


def test_every_page_has_a_private_image(ingested, local_storage):
    images = DocumentAsset.objects.filter(
        version=ingested, asset_type=DocumentAsset.AssetType.PAGE_IMAGE
    )

    assert images.count() == 3
    for image in images:
        assert image.visibility == DocumentAsset.Visibility.PRIVATE
        assert image.page_id is not None
        assert (local_storage / image.storage_key).is_file()


@needs_tesseract
def test_no_index_record_is_left_queued(ingested):
    records = SearchIndexRecord.objects.filter(page__version=ingested)

    assert records.count() == 3
    assert not records.filter(status=SearchIndexRecord.Status.QUEUED).exists()
    assert records.filter(status=SearchIndexRecord.Status.INDEXED).count() == 3


@needs_tesseract
def test_the_ocr_text_is_searchable(ingested):
    """La finalisation doit courir apres l'OCR, sinon le texte reconnu
    n'atteint jamais l'index du document."""
    results = search_documents(query="NUMERISE")

    assert [result["document_id"] for result in results] == [ingested.document_id]


def test_a_reader_session_serves_a_page_with_no_storage_field(ingested, client):
    session = client.post(
        reverse("api-v1:reader-session-create"),
        data={"document_id": ingested.document_id},
        content_type="application/json",
    )
    assert session.status_code == 201
    session_key = session.json()["session_key"]

    response = client.get(
        reverse(
            "api-v1:reader-page",
            kwargs={"session_key": session_key, "page_number": 1},
        )
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Architecture" in payload["text"]
    assert set(payload) == {
        "session_key",
        "document_id",
        "version_id",
        "page_number",
        "page_count",
        "language_code",
        "text",
    }
    assert "storage" not in response.content.decode().lower()


def test_ingesting_inline_produces_the_same_result(local_storage, db):
    """Le mode --sync d'ingest_file doit converger vers le meme etat, pour
    un contributeur qui n'a pas de worker sous la main."""
    domain = AcademicDomain.objects.create(name="Droit", slug="droit-sync")
    document = Document.objects.create(
        title="Ingestion en ligne",
        slug="ingestion-en-ligne",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )

    with FIXTURE.open("rb") as handle:
        version = ingest_document_file(
            document=document,
            fileobj=handle,
            original_filename="sample.pdf",
            dispatch=False,
        )

    assert version.status == "processed"
    assert version.page_count == 3
    assert DocumentPage.objects.filter(version=version).count() == 3
    assert not SearchIndexRecord.objects.filter(
        page__version=version, status=SearchIndexRecord.Status.QUEUED
    ).exists()
