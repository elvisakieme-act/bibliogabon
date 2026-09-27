from __future__ import annotations

from pathlib import Path

import pytest

from catalog.models import AcademicDomain, Document
from document_ingestion import tasks
from document_ingestion.models import DocumentVersion
from document_ingestion.pipeline import ingest_document_file
from document_ingestion.tests.ingestion_helpers import ingest_source_only
from document_processing.models import DocumentPage, ExtractedText, SearchIndexRecord
from search_discovery.models import DocumentSearchIndex
from search_discovery.services import search_documents

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "document_ingestion"
    / "tests"
    / "fixtures"
    / "sample-3-pages.pdf"
)


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def version(local_storage, db):
    """Le fixture a trois pages dont la troisieme, rendue en image, ressort
    avec un texte de remplacement : exactement le cas a ne pas indexer."""
    domain = AcademicDomain.objects.create(name="Reseaux", slug="reseaux-index")
    document = Document.objects.create(
        title="Document a indexer",
        slug="document-a-indexer",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )
    with FIXTURE.open("rb") as handle:
        return ingest_document_file(
            document=document, fileobj=handle, original_filename="sample.pdf"
        )


def test_a_full_ingestion_leaves_no_record_queued(version):
    """La file avait 157 lignes queued et aucun consommateur : c'etait le
    deuxieme defaut releve sur le pilier."""
    records = SearchIndexRecord.objects.filter(page__version=version)

    assert records.count() == 3
    assert not records.filter(status=SearchIndexRecord.Status.QUEUED).exists()


def test_index_page_moves_a_record_from_queued_to_indexed(version):
    page = DocumentPage.objects.get(version=version, page_number=1)
    record = SearchIndexRecord.objects.get(page=page)
    record.status = SearchIndexRecord.Status.QUEUED
    record.indexed_at = None
    record.save()

    tasks.index_page.apply(args=[page.pk]).get()

    record.refresh_from_db()
    assert record.status == SearchIndexRecord.Status.INDEXED
    assert record.indexed_at is not None
    assert record.error_code == ""


def test_a_placeholder_page_is_recorded_as_failed_not_indexed(local_storage, db):
    """Sur une ingestion source seule, la page 3 reste un placeholder :
    c'est l'etat que le consommateur doit refuser d'indexer."""
    from document_ingestion.tasks import index_page

    domain = AcademicDomain.objects.create(name="Brut", slug="brut")
    document = Document.objects.create(
        title="Sans OCR",
        slug="sans-ocr",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )
    raw = ingest_source_only(document, FIXTURE.read_bytes())
    page = DocumentPage.objects.get(version=raw, page_number=3)

    index_page.apply(args=[page.pk]).get()

    record = SearchIndexRecord.objects.get(page=page)
    assert record.status == SearchIndexRecord.Status.FAILED
    assert record.error_code == "no_extractable_text"


def test_index_page_is_idempotent(version):
    page = DocumentPage.objects.get(version=version, page_number=1)
    tasks.index_page.apply(args=[page.pk]).get()
    first = SearchIndexRecord.objects.get(page=page).indexed_at

    tasks.index_page.apply(args=[page.pk]).get()

    assert SearchIndexRecord.objects.get(page=page).indexed_at == first


def test_a_page_without_text_fails_its_record(version):
    page = DocumentPage.objects.get(version=version, page_number=2)
    ExtractedText.objects.filter(page=page).delete()

    tasks.index_page.apply(args=[page.pk]).get()

    record = SearchIndexRecord.objects.get(page=page)
    assert record.status == SearchIndexRecord.Status.FAILED
    assert record.error_code == "no_extracted_text"


def test_placeholder_text_never_reaches_the_document_index(local_storage, db):
    from document_ingestion.services import mark_version_current_and_index

    domain = AcademicDomain.objects.create(name="Brut", slug="brut-index")
    document = Document.objects.create(
        title="Sans OCR indexe",
        slug="sans-ocr-indexe",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )
    raw = ingest_source_only(document, FIXTURE.read_bytes())
    mark_version_current_and_index(raw)

    index = DocumentSearchIndex.objects.get(document=document)
    assert "aucun texte extractible" not in index.page_text
    assert index.indexed_page_count == 2, "seules les deux pages lisibles comptent"


def test_searching_the_placeholder_wording_finds_nothing(version):
    assert search_documents(query="aucun texte extractible") == []
    assert search_documents(query="OCR requis") == []


def test_real_page_text_is_still_searchable(version):
    results = search_documents(query="Architecture")

    assert [result["document_id"] for result in results] == [version.document_id]
    assert results[0]["text_match"] is True


def test_finalize_version_flips_is_current_and_rebuilds_once(version, local_storage):
    older = DocumentVersion.objects.create(
        document=version.document, version_label="v0", is_current=True
    )

    tasks.finalize_version.apply(args=[version.pk]).get()

    older.refresh_from_db()
    version.refresh_from_db()
    assert version.is_current is True
    assert older.is_current is False
    assert DocumentSearchIndex.objects.filter(document=version.document).count() == 1
