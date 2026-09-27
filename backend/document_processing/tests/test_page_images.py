from __future__ import annotations

import io
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError

from catalog.models import AcademicDomain, Document
from document_ingestion import tasks
from document_ingestion.models import DocumentAsset, DocumentVersion
from document_ingestion.pipeline import ingest_document_file
from document_processing.models import DocumentPage

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
    settings.DOCUMENT_PAGE_IMAGE_WIDTH = 620
    return tmp_path


@pytest.fixture
def version(local_storage, db):
    domain = AcademicDomain.objects.create(name="Reseaux", slug="reseaux-images")
    document = Document.objects.create(
        title="Document a rendre",
        slug="document-a-rendre",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )
    with FIXTURE.open("rb") as handle:
        return ingest_document_file(
            document=document, fileobj=handle, original_filename="sample.pdf"
        )


def test_rendering_creates_one_private_asset_linked_to_the_page(version, local_storage):
    page = DocumentPage.objects.get(version=version, page_number=2)

    tasks.render_page_image.apply(args=[page.pk]).get()

    asset = DocumentAsset.objects.get(page=page)
    assert asset.asset_type == DocumentAsset.AssetType.PAGE_IMAGE
    assert asset.visibility == DocumentAsset.Visibility.PRIVATE
    assert asset.version_id == version.pk
    assert asset.mime_type == "image/webp"
    assert asset.byte_size > 0
    assert (local_storage / asset.storage_key).is_file()


def test_the_stored_object_is_a_webp_at_the_configured_width(version, local_storage):
    from PIL import Image

    page = DocumentPage.objects.get(version=version, page_number=1)

    tasks.render_page_image.apply(args=[page.pk]).get()

    asset = DocumentAsset.objects.get(page=page)
    with (local_storage / asset.storage_key).open("rb") as handle:
        image = Image.open(io.BytesIO(handle.read()))
    assert image.format == "WEBP"
    assert image.width == 620


def test_rendering_twice_does_not_duplicate_the_asset(version, local_storage):
    page = DocumentPage.objects.get(version=version, page_number=1)

    tasks.render_page_image.apply(args=[page.pk]).get()
    first = DocumentAsset.objects.get(page=page)
    tasks.render_page_image.apply(args=[page.pk]).get()

    assert DocumentAsset.objects.filter(page=page).count() == 1
    second = DocumentAsset.objects.get(page=page)
    assert second.pk == first.pk
    assert second.checksum_sha256 == first.checksum_sha256


def test_two_identical_pages_each_keep_their_own_image(local_storage, db):
    """Deux pages au contenu identique produisent le meme checksum. La
    contrainte d'unicite par version aurait refuse la seconde."""
    import pymupdf

    document_pdf = pymupdf.open()
    for _ in range(2):
        document_pdf.new_page()  # deux pages vides, donc identiques
    domain = AcademicDomain.objects.create(name="Vide", slug="vide")
    document = Document.objects.create(
        title="Pages identiques",
        slug="pages-identiques",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )
    version = ingest_document_file(
        document=document,
        fileobj=io.BytesIO(document_pdf.tobytes()),
        original_filename="vide.pdf",
    )

    for number in (1, 2):
        page = DocumentPage.objects.get(version=version, page_number=number)
        tasks.render_page_image.apply(args=[page.pk]).get()

    images = DocumentAsset.objects.filter(
        version=version, asset_type=DocumentAsset.AssetType.PAGE_IMAGE
    )
    assert images.count() == 2
    assert len({image.checksum_sha256 for image in images}) == 1, "contenu identique attendu"


def test_source_asset_idempotency_still_holds(version):
    """La contrainte d'origine protege toujours les fichiers source."""
    sources = DocumentAsset.objects.filter(
        version=version, asset_type=DocumentAsset.AssetType.SOURCE_PDF
    )
    assert sources.count() == 1


def test_an_asset_cannot_point_at_a_page_from_another_version(version, local_storage, db):
    other = DocumentVersion.objects.create(document=version.document, version_label="v2")
    page = DocumentPage.objects.get(version=version, page_number=1)

    asset = DocumentAsset(
        version=other,
        page=page,
        asset_type=DocumentAsset.AssetType.PAGE_IMAGE,
        storage_bucket="bucket",
        storage_key="documents/1/versions/v2/pages/0001.webp",
        mime_type="image/webp",
        byte_size=10,
        checksum_sha256="a" * 64,
    )

    with pytest.raises(ValidationError):
        asset.save()


def test_page_images_never_reach_a_public_payload(version, local_storage, client):
    """Les images de page sont des derives d'un fichier prive : aucune
    reponse publique ne doit les nommer, ni exposer une cle ou une URL."""
    from django.urls import reverse

    page = DocumentPage.objects.get(version=version, page_number=1)
    tasks.render_page_image.apply(args=[page.pk]).get()
    asset = DocumentAsset.objects.get(page=page)

    document = version.document
    document.publication_status = Document.PublicationStatus.PUBLISHED
    document.save()

    session = client.post(
        reverse("api-v1:reader-session-create"),
        data={"document_id": document.pk},
        content_type="application/json",
    )
    assert session.status_code == 201
    session_key = session.json()["session_key"]

    payloads = [
        session.content.decode(),
        client.get(
            reverse(
                "api-v1:reader-page",
                kwargs={"session_key": session_key, "page_number": 1},
            )
        ).content.decode(),
        client.get(
            reverse("api-v1:catalog-document-detail", kwargs={"document_id": document.pk})
        ).content.decode(),
        client.get(reverse("api-v1:catalog-documents")).content.decode(),
        client.get(reverse("api-v1:search")).content.decode(),
    ]

    for payload in payloads:
        assert "page_image" not in payload
        assert asset.storage_key not in payload
        assert ".webp" not in payload
        assert "storage" not in payload.lower()
