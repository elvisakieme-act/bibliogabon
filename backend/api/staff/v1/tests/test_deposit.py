from __future__ import annotations

import io
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from api.staff.v1 import deposit as deposit_module
from catalog.models import AcademicDomain, Author, Document, DocumentAuthor, DocumentType
from document_ingestion.models import DocumentAsset


FIXTURE = Path(__file__).resolve().parents[4] / "document_ingestion" / "tests" / "fixtures" / "sample-3-pages.pdf"
SOURCE = "api-staff-v1:document-source"


def make_user(email: str, account_type: str) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type
    )


@pytest.fixture
def storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def teacher(db):
    return make_user("enseignant@example.ga", User.AccountType.TEACHER_AUTHOR)


@pytest.fixture
def document(db, teacher, storage):
    domain = AcademicDomain.objects.create(name="Reseaux", slug="reseaux")
    doc_type = DocumentType.objects.create(name="Cours", slug="cours")
    document = Document.objects.create(
        title="Comprendre la 4G", slug="comprendre-4g",
        academic_domain=domain, document_type=doc_type,
        category=Document.Category.VOLUNTARY_TEACHER_DEPOSIT,
        access_model=Document.AccessModel.FREE,
    )
    author = Author.objects.create(
        display_name=teacher.email, normalized_name=teacher.email, linked_user=teacher
    )
    DocumentAuthor.objects.create(
        document=document, author=author, role=DocumentAuthor.Role.AUTHOR
    )
    return document


@pytest.fixture
def api():
    return APIClient()


def pdf_upload(name: str = "cours.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, FIXTURE.read_bytes(), content_type="application/pdf")


def test_uploading_stores_the_file_privately_and_reports_the_version(
    api, teacher, document, storage
):
    api.force_authenticate(teacher)

    response = api.post(
        reverse(SOURCE, args=[document.pk]), {"file": pdf_upload()}, format="multipart"
    )

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["ingestion"]["page_count"] == 3
    asset = DocumentAsset.objects.get(
        version__document=document, asset_type=DocumentAsset.AssetType.SOURCE_PDF
    )
    assert asset.visibility == DocumentAsset.Visibility.PRIVATE
    assert (storage / asset.storage_key).is_file()


def test_the_response_never_leaks_a_path_or_a_url(api, teacher, document, storage):
    api.force_authenticate(teacher)

    body = api.post(
        reverse(SOURCE, args=[document.pk]), {"file": pdf_upload()}, format="multipart"
    ).content.decode()

    assert "storage" not in body.lower()
    assert ".pdf" not in body
    assert "://" not in body


def test_a_file_above_the_limit_is_refused(api, teacher, document, settings, storage):
    settings.DOCUMENT_UPLOAD_MAX_BYTES = 1024
    api.force_authenticate(teacher)

    response = api.post(
        reverse(SOURCE, args=[document.pk]), {"file": pdf_upload()}, format="multipart"
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_a_refused_upload_writes_nothing(api, teacher, document, settings, storage):
    settings.DOCUMENT_UPLOAD_MAX_BYTES = 1024
    api.force_authenticate(teacher)

    api.post(reverse(SOURCE, args=[document.pk]), {"file": pdf_upload()}, format="multipart")

    assert not DocumentAsset.objects.filter(version__document=document).exists()
    assert list(storage.rglob("*")) == [], "un refus ne doit rien laisser en stockage"


def test_an_unaccepted_type_is_refused(api, teacher, document, storage):
    api.force_authenticate(teacher)
    upload = SimpleUploadedFile("notes.txt", b"du texte", content_type="text/plain")

    response = api.post(
        reverse(SOURCE, args=[document.pk]), {"file": upload}, format="multipart"
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_a_second_upload_conflicts_and_replace_succeeds(api, teacher, document, storage):
    api.force_authenticate(teacher)
    api.post(reverse(SOURCE, args=[document.pk]), {"file": pdf_upload()}, format="multipart")

    conflict = api.post(
        reverse(SOURCE, args=[document.pk]), {"file": pdf_upload("autre.pdf")}, format="multipart"
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "version_already_ingested"

    replaced = api.post(
        f"{reverse(SOURCE, args=[document.pk])}?replace=true",
        {"file": pdf_upload("autre.pdf")},
        format="multipart",
    )
    assert replaced.status_code == 201, replaced.json()


def test_a_large_upload_reaches_the_service_as_a_temporary_file(
    api, teacher, document, monkeypatch, settings, storage
):
    """La taille est le point de bascule : au-dela de FILE_UPLOAD_MAX_MEMORY_SIZE
    Django doit passer un fichier temporaire, sinon le PDF transite en memoire."""
    seen = {}

    def capture(*, document, fileobj, **kwargs):
        seen["type"] = type(fileobj)
        seen["seekable"] = fileobj.seekable()
        from document_ingestion.models import DocumentVersion

        return DocumentVersion.objects.create(document=document, version_label="v1")

    monkeypatch.setattr(deposit_module, "ingest_document_file", capture)
    big = SimpleUploadedFile(
        "gros.pdf",
        b"%PDF-1.4 " + b"x" * (settings.FILE_UPLOAD_MAX_MEMORY_SIZE + 1024),
        content_type="application/pdf",
    )
    api.force_authenticate(teacher)

    api.post(reverse(SOURCE, args=[document.pk]), {"file": big}, format="multipart")

    assert seen["type"] is TemporaryUploadedFile, seen
    assert seen["seekable"] is True


def test_a_teacher_cannot_upload_to_someone_elses_document(api, document, storage):
    intruder = make_user("intrus@example.ga", User.AccountType.TEACHER_AUTHOR)
    api.force_authenticate(intruder)

    response = api.post(
        reverse(SOURCE, args=[document.pk]), {"file": pdf_upload()}, format="multipart"
    )

    assert response.status_code == 404


def test_a_student_cannot_upload(api, document, storage):
    api.force_authenticate(make_user("etudiant@example.ga", User.AccountType.INDIVIDUAL))

    response = api.post(
        reverse(SOURCE, args=[document.pk]), {"file": pdf_upload()}, format="multipart"
    )

    assert response.status_code == 403


def test_a_teacher_cannot_replace_the_source_of_a_published_document(
    api, teacher, document, storage
):
    """Remplacer la source d'un document publie doit repasser par un
    moderateur : le contenu diffuse a deja ete valide."""
    document.publication_status = Document.PublicationStatus.PUBLISHED
    document.save(update_fields=["publication_status"])
    api.force_authenticate(teacher)

    response = api.post(
        reverse(SOURCE, args=[document.pk]), {"file": pdf_upload()}, format="multipart"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_locked"


def test_a_moderator_may_replace_the_source_of_a_published_document(
    api, document, storage
):
    document.publication_status = Document.PublicationStatus.PUBLISHED
    document.save(update_fields=["publication_status"])
    api.force_authenticate(make_user("mod@bibliogabon.ga", User.AccountType.CONTENT_ADMIN))

    response = api.post(
        reverse(SOURCE, args=[document.pk]), {"file": pdf_upload()}, format="multipart"
    )

    assert response.status_code == 201, response.json()


def test_an_upload_without_a_file_is_refused(api, teacher, document, storage):
    api.force_authenticate(teacher)

    response = api.post(reverse(SOURCE, args=[document.pk]), {}, format="multipart")

    assert response.status_code == 400
    assert "file" in response.json()["error"]["field_errors"]
