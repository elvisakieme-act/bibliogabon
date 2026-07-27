import pytest
from django.core.exceptions import ValidationError

from catalog.models import AcademicDomain, Author, Document, DocumentAuthor
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_processing.services import attach_extracted_text, create_page_records
from search_discovery.models import DocumentSearchIndex


def create_document(slug="search-index-document"):
    domain = AcademicDomain.objects.create(name=f"Education {slug}", slug=f"education-{slug}")
    return Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        abstract="Analyse des pratiques academiques.",
        language_code="fr",
        publication_year=2026,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )


def add_author(document, display_name, position):
    author = Author.objects.create(
        display_name=display_name,
        normalized_name=display_name.lower(),
    )
    DocumentAuthor.objects.create(document=document, author=author, position=position)
    return author


def create_processed_version(document, version_label="v1", is_current=True, page_count=1):
    return DocumentVersion.objects.create(
        document=document,
        version_label=version_label,
        status=DocumentVersion.Status.PROCESSED,
        is_current=is_current,
        page_count=page_count,
    )


def add_page_text(version, page_number, text, status=DocumentPage.Status.PROCESSED):
    pages = create_page_records(version=version, page_count=version.page_count)
    page = pages[page_number - 1]
    page.status = status
    page.save(update_fields=["status", "updated_at"])
    attach_extracted_text(page=page, text=text, language_code="fr")
    return page


@pytest.mark.django_db
def test_document_search_index_stores_safe_denormalized_metadata():
    document = create_document()

    index = DocumentSearchIndex.objects.create(
        document=document,
        title="Pedagogie universitaire",
        slug="pedagogie-universitaire",
        abstract="Analyse des pratiques.",
        language_code="fr",
        publication_year=2026,
        access_model=Document.AccessModel.FREE,
        domain_name="Education",
        domain_slug="education",
        author_names="Aline NZE\nBrice ONDO",
        metadata_text="Pedagogie universitaire Analyse des pratiques.",
        page_text="Texte interne non expose.",
        indexed_page_count=1,
    )

    assert index.document == document
    assert index.title == "Pedagogie universitaire"
    assert index.author_names.splitlines() == ["Aline NZE", "Brice ONDO"]
    assert index.page_text == "Texte interne non expose."


@pytest.mark.django_db
def test_document_search_index_rejects_blank_title():
    document = create_document(slug="blank-title-document")
    index = DocumentSearchIndex(
        document=document,
        title="   ",
        slug="blank-title-document",
        language_code="fr",
        access_model=Document.AccessModel.FREE,
    )

    with pytest.raises(ValidationError):
        index.save()


@pytest.mark.django_db
def test_rebuild_document_search_index_copies_published_metadata_and_ordered_authors():
    from search_discovery.services import rebuild_document_search_index

    document = create_document(slug="metadata-copy")
    document.title = "Pedagogie universitaire au Gabon"
    document.save(update_fields=["title", "updated_at"])
    add_author(document, "Brice ONDO", position=2)
    add_author(document, "Aline NZE", position=1)

    index = rebuild_document_search_index(document)

    assert index.document == document
    assert index.title == "Pedagogie universitaire au Gabon"
    assert index.slug == "metadata-copy"
    assert index.domain_name == "Education metadata-copy"
    assert index.domain_slug == "education-metadata-copy"
    assert index.author_names.splitlines() == ["Aline NZE", "Brice ONDO"]
    assert "Pedagogie universitaire au Gabon" in index.metadata_text
    assert "Aline NZE" in index.metadata_text


@pytest.mark.parametrize(
    ("publication_status", "access_model"),
    [
        (Document.PublicationStatus.DRAFT, Document.AccessModel.FREE),
        (Document.PublicationStatus.WITHDRAWN, Document.AccessModel.FREE),
        (Document.PublicationStatus.SUSPENDED, Document.AccessModel.FREE),
        (Document.PublicationStatus.PUBLISHED, Document.AccessModel.PRIVATE),
    ],
)
@pytest.mark.django_db
def test_rebuild_document_search_index_removes_non_discoverable_documents(publication_status, access_model):
    from search_discovery.services import rebuild_document_search_index

    document = create_document(slug=f"non-discoverable-{publication_status}-{access_model}")
    DocumentSearchIndex.objects.create(
        document=document,
        title=document.title,
        slug=document.slug,
        language_code=document.language_code,
        access_model=document.access_model,
    )
    document.publication_status = publication_status
    document.access_model = access_model
    document.save(update_fields=["publication_status", "access_model", "updated_at"])

    index = rebuild_document_search_index(document)

    assert index is None
    assert not DocumentSearchIndex.objects.filter(document=document).exists()


@pytest.mark.django_db
def test_rebuild_document_search_index_uses_current_processed_version_processed_pages_only():
    from search_discovery.services import rebuild_document_search_index

    document = create_document(slug="processed-pages")
    old_version = create_processed_version(document, version_label="old", is_current=False, page_count=1)
    add_page_text(old_version, 1, "Archive ancienne non indexee.")
    current_version = create_processed_version(document, version_label="current", is_current=True, page_count=2)
    add_page_text(current_version, 1, "Cellules solaires et reseaux ruraux.")
    add_page_text(
        current_version,
        2,
        "Brouillon technique non indexe.",
        status=DocumentPage.Status.PENDING,
    )

    index = rebuild_document_search_index(document)

    assert index.indexed_page_count == 1
    assert "Cellules solaires" in index.page_text
    assert "Archive ancienne" not in index.page_text
    assert "Brouillon technique" not in index.page_text


@pytest.mark.django_db
def test_rebuild_all_document_search_indexes_counts_discoverable_documents():
    from search_discovery.services import rebuild_all_document_search_indexes

    create_document(slug="published-free")
    private_document = create_document(slug="private-document")
    private_document.access_model = Document.AccessModel.PRIVATE
    private_document.save(update_fields=["access_model", "updated_at"])
    draft_document = create_document(slug="draft-document")
    draft_document.publication_status = Document.PublicationStatus.DRAFT
    draft_document.save(update_fields=["publication_status", "updated_at"])

    indexed_count = rebuild_all_document_search_indexes()

    assert indexed_count == 1
    assert list(DocumentSearchIndex.objects.values_list("document__slug", flat=True)) == ["published-free"]
