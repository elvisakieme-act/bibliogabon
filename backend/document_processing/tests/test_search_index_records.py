import pytest

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_processing.models import SearchIndexRecord
from document_processing.services import attach_extracted_text, create_page_records, queue_page_index_record


def create_page():
    domain = AcademicDomain.objects.create(name="Indexation", slug="indexation")
    document = Document.objects.create(
        title="Index pedagogique",
        slug="index-pedagogique",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.PRIVATE,
    )
    version = DocumentVersion.objects.create(document=document, version_label="v1")
    return create_page_records(version=version, page_count=1)[0]


@pytest.mark.django_db
def test_queue_page_index_record_requires_extracted_text():
    with pytest.raises(ValueError):
        queue_page_index_record(page=create_page())


@pytest.mark.django_db
def test_queue_page_index_record_creates_queued_record_with_text_hash():
    page = create_page()
    attach_extracted_text(page=page, text="Texte indexable.", language_code="fr")

    record = queue_page_index_record(page=page)

    assert record.page == page
    assert record.status == SearchIndexRecord.Status.QUEUED
    assert record.language_code == "fr"
    assert record.content_hash == "209fc5a8ab892d41a6c01f8f50b03d3cc0286c66704ea6a3ad7c1f7eae1941a0"
    assert record.indexed_at is None


@pytest.mark.django_db
def test_queue_page_index_record_is_idempotent_for_unchanged_text():
    page = create_page()
    attach_extracted_text(page=page, text="Texte indexable.", language_code="fr")
    first = queue_page_index_record(page=page)

    second = queue_page_index_record(page=page)

    assert second.pk == first.pk
    assert SearchIndexRecord.objects.count() == 1
    assert second.content_hash == first.content_hash


@pytest.mark.django_db
def test_queue_page_index_record_refreshes_hash_when_text_changes():
    page = create_page()
    attach_extracted_text(page=page, text="Texte indexable.", language_code="fr")
    record = queue_page_index_record(page=page)
    record.status = SearchIndexRecord.Status.INDEXED
    record.save(update_fields=["status", "updated_at"])

    attach_extracted_text(page=page, text="Texte modifie.", language_code="fr")
    refreshed = queue_page_index_record(page=page)

    assert refreshed.pk == record.pk
    assert refreshed.status == SearchIndexRecord.Status.QUEUED
    assert refreshed.content_hash == "6e1a717bf3eaf63bdb9986805bdafaea43ec0b0d79a4ba6f52206f540d8b5728"
