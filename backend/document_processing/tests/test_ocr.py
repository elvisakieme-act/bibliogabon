from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from catalog.models import AcademicDomain, Document
from document_ingestion import tasks
from document_ingestion.tests.ingestion_helpers import (
    ingest_source_only,
    tesseract_marker,
)
from document_processing.models import DocumentPage, ExtractedText, SearchIndexRecord

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "document_ingestion"
    / "tests"
    / "fixtures"
    / "sample-3-pages.pdf"
)

needs_tesseract = tesseract_marker()


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    settings.OCR_LANGUAGES = "fra"
    settings.OCR_MIN_CHARACTERS = 20
    return tmp_path


@pytest.fixture
def scanned_version(local_storage, db):
    domain = AcademicDomain.objects.create(name="Reseaux", slug="reseaux-ocr")
    document = Document.objects.create(
        title="Document partiellement numerise",
        slug="document-numerise",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )
    # Source seule : la chaine complete passerait l'OCR d'elle-meme et il
    # n'y aurait plus de placeholder a observer.
    return ingest_source_only(document, FIXTURE.read_bytes())


def test_the_fixture_really_has_a_page_without_a_text_layer(scanned_version):
    """Sans cette page, le test d'OCR ne prouverait rien."""
    texts = {
        text.page.page_number: text
        for text in ExtractedText.objects.filter(page__version=scanned_version)
    }
    assert len(texts) == 3
    assert "Architecture" in texts[1].text
    assert texts[3].text.startswith("[Page 3"), "la page 3 devrait etre un placeholder"


def test_pages_with_a_text_layer_are_not_sent_to_ocr(scanned_version):
    page = DocumentPage.objects.get(version=scanned_version, page_number=1)

    assert tasks.page_needs_ocr(page) is False


def test_a_page_below_the_threshold_is_routed_to_ocr(scanned_version):
    page = DocumentPage.objects.get(version=scanned_version, page_number=3)

    assert tasks.page_needs_ocr(page) is True


@needs_tesseract
def test_ocr_replaces_the_placeholder_and_records_its_provenance(scanned_version):
    page = DocumentPage.objects.get(version=scanned_version, page_number=3)

    tasks.ocr_page.apply(args=[page.pk]).get()

    text = ExtractedText.objects.get(page=page)
    assert "NUMERISE" in text.text.upper()
    assert not text.text.startswith("[Page")
    assert text.extraction_method == ExtractedText.ExtractionMethod.OCR
    assert text.confidence is not None
    assert Decimal("0") <= text.confidence <= Decimal("1")


@needs_tesseract
def test_ocr_output_is_normalised_like_any_other_text(scanned_version):
    page = DocumentPage.objects.get(version=scanned_version, page_number=3)

    tasks.ocr_page.apply(args=[page.pk]).get()

    text = ExtractedText.objects.get(page=page).text
    assert not any(ord(character) < 32 and character not in "\n\t" for character in text)


@needs_tesseract
def test_ocr_requeues_the_page_for_indexing(scanned_version):
    page = DocumentPage.objects.get(version=scanned_version, page_number=3)
    before = SearchIndexRecord.objects.get(page=page).content_hash

    tasks.ocr_page.apply(args=[page.pk]).get()

    record = SearchIndexRecord.objects.get(page=page)
    assert record.content_hash != before, "le texte a change, l'index doit etre rafraichi"
    assert record.status == SearchIndexRecord.Status.QUEUED


@needs_tesseract
def test_replaying_ocr_on_a_recognised_page_changes_nothing(scanned_version):
    page = DocumentPage.objects.get(version=scanned_version, page_number=3)
    tasks.ocr_page.apply(args=[page.pk]).get()
    first = ExtractedText.objects.get(page=page)

    tasks.ocr_page.apply(args=[page.pk]).get()

    second = ExtractedText.objects.get(page=page)
    assert second.text == first.text
    assert second.updated_at == first.updated_at, "la page a ete retraitee"


@needs_tesseract
def test_ocr_skips_a_page_that_already_has_a_text_layer(scanned_version):
    page = DocumentPage.objects.get(version=scanned_version, page_number=1)
    before = ExtractedText.objects.get(page=page)

    tasks.ocr_page.apply(args=[page.pk]).get()

    after = ExtractedText.objects.get(page=page)
    assert after.extraction_method == ExtractedText.ExtractionMethod.TEXT_LAYER
    assert after.updated_at == before.updated_at


def test_an_unreadable_page_keeps_its_placeholder_and_fails_its_index_record(
    scanned_version, monkeypatch
):
    """Le cas vise est « l'OCR a tourne et n'a rien reconnu », pas « le
    binaire manque » — ce dernier est couvert par le test suivant, et sort
    plus tot sans marquer l'index en echec. Sans ce `which` force, le test
    passait sur une machine equipee et echouait en CI, qui n'installait pas
    tesseract : rouge pendant vingt-huit executions."""
    page = DocumentPage.objects.get(version=scanned_version, page_number=3)
    monkeypatch.setattr(tasks.shutil, "which", lambda name: "/usr/bin/tesseract")
    monkeypatch.setattr(tasks, "recognise_page", lambda *a, **k: ("", None))

    tasks.ocr_page.apply(args=[page.pk]).get()

    text = ExtractedText.objects.get(page=page)
    assert text.text.startswith("[Page 3"), "le placeholder doit rester visible"
    record = SearchIndexRecord.objects.get(page=page)
    assert record.status == SearchIndexRecord.Status.FAILED
    assert record.error_code


def test_missing_tesseract_is_reported_without_crashing(scanned_version, monkeypatch, caplog):
    page = DocumentPage.objects.get(version=scanned_version, page_number=3)
    monkeypatch.setattr(tasks.shutil, "which", lambda name: None)

    with caplog.at_level("WARNING"):
        tasks.ocr_page.apply(args=[page.pk]).get()

    assert "tesseract" in caplog.text.lower()
    assert ExtractedText.objects.get(page=page).text.startswith("[Page 3")
