import pytest

from accounts.models import Organization
from catalog.models import AcademicDomain, Author, Document, DocumentAuthor


@pytest.mark.django_db
def test_document_stores_metadata_and_ordered_authors():
    domain = AcademicDomain.objects.create(name="Education", slug="education")
    owner = Organization.objects.create(name="Universite Omar Bongo", slug="uob")
    document = Document.objects.create(
        title="Pedagogie universitaire au Gabon",
        slug="pedagogie-universitaire-gabon",
        abstract="Analyse des pratiques pedagogiques universitaires.",
        language_code="fr",
        publication_year=2026,
        academic_domain=domain,
        owner_organization=owner,
        category=Document.Category.INSTITUTIONAL_FUND,
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    first = Author.objects.create(display_name="Aline NZE", normalized_name="nze aline")
    second = Author.objects.create(display_name="Brice ONDO", normalized_name="ondo brice")

    DocumentAuthor.objects.create(
        document=document,
        author=first,
        role=DocumentAuthor.Role.AUTHOR,
        position=1,
    )
    DocumentAuthor.objects.create(
        document=document,
        author=second,
        role=DocumentAuthor.Role.SUPERVISOR,
        position=2,
    )

    author_names = list(
        document.document_authors.order_by("position").values_list(
            "author__display_name",
            flat=True,
        )
    )

    assert str(document) == "Pedagogie universitaire au Gabon"
    assert document.publication_status == Document.PublicationStatus.DRAFT
    assert document.entitlement_scope_id == str(document.pk)
    assert author_names == ["Aline NZE", "Brice ONDO"]
