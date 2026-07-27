import pytest

from catalog.models import AcademicDomain, Document
from document_ingestion.storage import build_private_storage_key, storage_key_is_public_reference


@pytest.mark.django_db
def test_private_storage_key_is_deterministic_and_not_public_url():
    domain = AcademicDomain.objects.create(name="Informatique", slug="informatique-ingestion")
    document = Document.objects.create(
        title="Architecture numerique",
        slug="architecture-numerique",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.PRIVATE,
    )

    storage_key = build_private_storage_key(
        document=document,
        version_label="v1",
        original_filename="Memoire Final.pdf",
        checksum_sha256="a" * 64,
    )

    assert storage_key == f"documents/{document.pk}/versions/v1/aaaaaaaa/memoire-final.pdf"
    assert storage_key_is_public_reference(storage_key) is False


@pytest.mark.parametrize(
    "value",
    [
        "http://example.com/file.pdf",
        "https://example.com/file.pdf",
        "file:///tmp/file.pdf",
    ],
)
def test_public_references_are_rejected(value):
    assert storage_key_is_public_reference(value) is True
