import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentAsset, DocumentVersion


def create_document():
    domain = AcademicDomain.objects.create(name="Droit numerique", slug="droit-numerique")
    return Document.objects.create(
        title="Droit numerique gabonais",
        slug="droit-numerique-gabonais",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.PRIVATE,
    )


@pytest.mark.django_db
def test_document_version_is_unique_per_document_and_label():
    document = create_document()
    DocumentVersion.objects.create(document=document, version_label="v1")

    with pytest.raises(IntegrityError):
        DocumentVersion.objects.create(document=document, version_label="v1")


@pytest.mark.django_db
def test_source_asset_stores_private_object_metadata():
    version = DocumentVersion.objects.create(document=create_document(), version_label="v1")
    asset = DocumentAsset.objects.create(
        version=version,
        asset_type=DocumentAsset.AssetType.SOURCE_PDF,
        storage_bucket="bibliogabon-private-documents",
        storage_key="documents/1/versions/v1/abcd1234/source.pdf",
        mime_type="application/pdf",
        byte_size=2048,
        checksum_sha256="b" * 64,
    )

    assert asset.visibility == DocumentAsset.Visibility.PRIVATE
    assert str(asset) == "source_pdf: documents/1/versions/v1/abcd1234/source.pdf"


@pytest.mark.parametrize(
    "storage_key",
    [
        "http://example.com/source.pdf",
        "https://example.com/source.pdf",
        "file:///tmp/source.pdf",
    ],
)
@pytest.mark.django_db
def test_asset_rejects_public_storage_reference(storage_key):
    version = DocumentVersion.objects.create(document=create_document(), version_label="v1")
    asset = DocumentAsset(
        version=version,
        asset_type=DocumentAsset.AssetType.SOURCE_PDF,
        storage_bucket="bibliogabon-private-documents",
        storage_key=storage_key,
        mime_type="application/pdf",
        byte_size=2048,
        checksum_sha256="c" * 64,
    )

    with pytest.raises(ValidationError):
        asset.full_clean()


@pytest.mark.django_db
def test_asset_save_rejects_public_storage_reference():
    version = DocumentVersion.objects.create(document=create_document(), version_label="v1")
    asset = DocumentAsset(
        version=version,
        asset_type=DocumentAsset.AssetType.SOURCE_PDF,
        storage_bucket="bibliogabon-private-documents",
        storage_key=" https://example.com/source.pdf",
        mime_type="application/pdf",
        byte_size=2048,
        checksum_sha256="d" * 64,
    )

    with pytest.raises(ValidationError):
        asset.save()
