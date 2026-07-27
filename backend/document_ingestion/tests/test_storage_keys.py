import pytest

from catalog.models import AcademicDomain, Document
from document_ingestion.storage import (
    build_private_storage_key,
    normalize_key_segment,
    storage_key_is_public_reference,
)


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


@pytest.mark.parametrize(
    "value",
    [
        " https://example.com/file.pdf",
        "//example.com/file.pdf",
        "s3://public-bucket/file.pdf",
        "../private/file.pdf",
    ],
)
def test_url_like_or_path_traversal_references_are_rejected(value):
    assert storage_key_is_public_reference(value) is True


def test_version_label_is_normalized_for_storage_key_segments():
    assert normalize_key_segment("Draft / Final .. 2026") == "draft-final-2026"


def test_slugify_filename_preserves_real_default_filename():
    from document_ingestion.storage import slugify_filename

    assert slugify_filename("default.pdf") == "default.pdf"
    assert slugify_filename("!!!.pdf") == "document.pdf"
