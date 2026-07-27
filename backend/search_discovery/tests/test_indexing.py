import pytest
from django.core.exceptions import ValidationError

from catalog.models import AcademicDomain, Document
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
