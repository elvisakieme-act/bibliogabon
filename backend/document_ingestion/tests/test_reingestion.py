from __future__ import annotations

import io

import pytest

from catalog.models import AcademicDomain, Document
from document_ingestion.exceptions import VersionAlreadyIngested
from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob
from document_ingestion.pipeline import ingest_document_file
from document_processing.models import DocumentPage, ExtractedText, SearchIndexRecord


def build_pdf(pages: int, marker: str = "contenu") -> bytes:
    import pymupdf

    document = pymupdf.open()
    for number in range(1, pages + 1):
        page = document.new_page()
        page.insert_text((72, 72), f"{marker} page {number}")
    return document.tobytes()


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def document(db):
    domain = AcademicDomain.objects.create(name="Reseaux mobiles", slug="reseaux-mobiles")
    return Document.objects.create(
        title="Document reingerable",
        slug="document-reingerable",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )


def ingest(document, *, pages: int, marker: str = "contenu", **kwargs):
    return ingest_document_file(
        document=document,
        fileobj=io.BytesIO(build_pdf(pages, marker)),
        original_filename="source.pdf",
        **kwargs,
    )


def test_reingesting_the_same_label_raises_instead_of_colliding(local_storage, document):
    first = ingest(document, pages=3)

    with pytest.raises(VersionAlreadyIngested) as caught:
        ingest(document, pages=5, marker="autre")

    # L'echec enregistre en production etait un ValueError opaque remontant de
    # create_page_records : « Existing page records conflict with requested
    # page_count ». L'appelant recoit desormais la version en cause.
    assert caught.value.version.pk == first.pk
    assert caught.value.version_label == "v1"
    assert "v1" in str(caught.value)


def test_a_refused_reingestion_leaves_the_existing_version_intact(local_storage, document):
    first = ingest(document, pages=3)

    with pytest.raises(VersionAlreadyIngested):
        ingest(document, pages=5, marker="autre")

    first.refresh_from_db()
    assert first.status == DocumentVersion.Status.PROCESSED
    assert first.page_count == 3
    assert DocumentPage.objects.filter(version=first).count() == 3


def test_replace_converges_to_a_single_clean_set(local_storage, document):
    first = ingest(document, pages=5)

    second = ingest(document, pages=2, marker="remplacement", replace=True)

    assert second.pk == first.pk, "le remplacement reutilise la version"
    assert DocumentVersion.objects.filter(document=document).count() == 1
    assert second.page_count == 2
    assert DocumentPage.objects.filter(version=second).count() == 2
    assert ExtractedText.objects.filter(page__version=second).count() == 2
    assert SearchIndexRecord.objects.filter(page__version=second).count() == 2
    assert DocumentAsset.objects.filter(version=second).count() == 1
    texts = ExtractedText.objects.filter(page__version=second)
    assert all("remplacement" in text.text for text in texts)


def test_replace_leaves_no_orphan_rows(local_storage, document):
    ingest(document, pages=5)

    ingest(document, pages=2, marker="remplacement", replace=True)

    assert DocumentPage.objects.filter(version__document=document).count() == 2
    assert ExtractedText.objects.filter(page__version__document=document).count() == 2
    assert SearchIndexRecord.objects.filter(page__version__document=document).count() == 2


def test_a_new_label_creates_a_second_version_and_keeps_the_first(local_storage, document):
    first = ingest(document, pages=3)

    second = ingest(document, pages=4, marker="v2", version_label="v2")

    assert second.pk != first.pk
    assert DocumentVersion.objects.filter(document=document).count() == 2

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.page_count == 3
    assert second.page_count == 4
    assert second.is_current is True
    assert first.is_current is False, "une seule version courante a la fois"


def test_replace_reuses_the_job_rather_than_piling_them_up(local_storage, document):
    ingest(document, pages=3)

    ingest(document, pages=3, replace=True)

    jobs = ProcessingJob.objects.filter(version__document=document)
    assert jobs.count() == 1
    assert jobs.first().status == ProcessingJob.Status.SUCCEEDED


def test_replace_removes_the_previous_private_object(
    local_storage, document, django_capture_on_commit_callbacks
):
    first = ingest(document, pages=3)
    old_key = DocumentAsset.objects.get(version=first).storage_key
    assert (local_storage / old_key).is_file()

    # La suppression des objets stockes est differee au commit : un rollback
    # ne doit pas laisser la base pointer vers des fichiers deja effaces.
    with django_capture_on_commit_callbacks(execute=True):
        second = ingest(document, pages=2, marker="remplacement", replace=True)
    new_key = DocumentAsset.objects.get(version=second).storage_key

    assert new_key != old_key
    assert not (local_storage / old_key).exists(), "le fichier source remplace reste en stockage"
    assert (local_storage / new_key).is_file()


def test_replace_works_on_a_document_that_has_been_read(
    local_storage, document, django_capture_on_commit_callbacks
):
    """Un document déjà lu doit rester remplaçable : le journal d'accès est
    une trace d'audit, pas un verrou sur le contenu."""
    from django.utils import timezone

    from document_ingestion.models import DocumentVersion as _Version
    from document_processing.models import DocumentPage as _Page
    from document_reader.models import PageAccessLog, ReaderSession

    first = ingest(document, pages=3)
    session = ReaderSession.objects.create(
        user=None,
        document=document,
        version=first,
        started_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(hours=1),
    )
    page = _Page.objects.get(version=first, page_number=1)
    PageAccessLog.objects.create(
        session=session, page=page, user=None, document=document, page_number=1
    )

    with django_capture_on_commit_callbacks(execute=True):
        second = ingest(document, pages=2, marker="remplacement", replace=True)

    assert second.page_count == 2
    log = PageAccessLog.objects.get(document=document)
    assert log.page_id is None, "le journal doit survivre a la page supprimee"
    assert log.page_number == 1, "la trace d'audit conserve le numero de page"
