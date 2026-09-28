"""Manifeste IIIF de la session de lecture.

Une seule requête donne au visualiseur tout ce qu'il faut pour ouvrir le
document : le nombre de pages, les dimensions de chacune, l'adresse de son
service d'images.

C'est ce qui rend l'architecture tenable, et pas seulement élégante. Sans
manifeste, un visualiseur qui met 157 pages en page lit 157 `info.json` à
l'ouverture — donc demande 157 fois l'autorisation, et **journalise le
document entier comme lu** avant que le lecteur ait tourné une page. Le
manifeste, lui, ne livre aucun contenu : des dimensions et des adresses.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from catalog.models import AcademicDomain, Document, DocumentType
from document_ingestion import tasks
from document_ingestion.pipeline import ingest_document_file
from document_processing.models import DocumentPage
from document_reader.models import PageAccessLog, ReaderSession

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "document_ingestion"
    / "tests"
    / "fixtures"
    / "sample-3-pages.pdf"
)


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    settings.DOCUMENT_PAGE_IMAGE_WIDTH = 600
    return tmp_path


@pytest.fixture
def session(db, local_storage):
    domain = AcademicDomain.objects.create(name="Manifeste", slug="manifeste")
    document_type = DocumentType.objects.create(name="Thèse", slug="these-manifeste")
    document = Document.objects.create(
        title="Document au manifeste",
        slug="document-manifeste",
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    with FIXTURE.open("rb") as handle:
        version = ingest_document_file(
            document=document, fileobj=handle, original_filename="s.pdf"
        )
    for page in DocumentPage.objects.filter(version=version):
        tasks.tile_page.apply(args=[page.pk]).get()
    return ReaderSession.objects.create(
        document=document,
        version=version,
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )


def manifest_path(session: ReaderSession) -> str:
    return reverse("api-v1:reader-manifest", kwargs={"session_key": str(session.session_key)})


@pytest.mark.django_db
def test_the_manifest_describes_every_page(client, session):
    manifest = client.get(manifest_path(session)).json()

    assert manifest["type"] == "Manifest"
    assert manifest["@context"] == "http://iiif.io/api/presentation/3/context.json"
    assert len(manifest["items"]) == session.version.page_count
    assert manifest["label"]["fr"] == ["Document au manifeste"]


@pytest.mark.django_db
def test_every_canvas_carries_real_dimensions(client, session):
    """Des dimensions inventées décaleraient la mise en page de tout le
    document : le visualiseur place chaque page d'après ce qu'on lui annonce."""
    manifest = client.get(manifest_path(session)).json()

    for canvas in manifest["items"]:
        assert canvas["width"] > 0 and canvas["height"] > 0
        body = canvas["items"][0]["items"][0]["body"]
        assert body["width"] == canvas["width"]
        assert body["height"] == canvas["height"]


@pytest.mark.django_db
def test_every_canvas_points_at_an_image_service_that_answers(client, session):
    manifest = client.get(manifest_path(session)).json()

    for canvas in manifest["items"]:
        service = canvas["items"][0]["items"][0]["body"]["service"][0]
        assert service["type"] == "ImageService3"
        assert service["profile"] == "level0"
        # Le service est décrit en entier : un visualiseur qui recalculerait
        # les facteurs d'échelle en tiendrait une seconde écriture, et
        # demanderait un jour des tuiles que l'ingestion n'a pas produites.
        assert service["tiles"][0]["scaleFactors"][0] == 1
        assert service["sizes"][0] == {"width": canvas["width"], "height": canvas["height"]}

        info = client.get(f"{service['id']}/info.json")
        assert info.status_code == 200
        assert info.json()["tiles"] == service["tiles"]
        assert info.json()["sizes"] == service["sizes"]


@pytest.mark.django_db
def test_reading_the_manifest_logs_no_page_as_read(client, session):
    """L'invariant qui justifie son existence.

    Le manifeste ne livre aucun contenu. S'il journalisait, ouvrir un cours de
    157 pages l'enregistrerait entièrement comme lu avant que le lecteur ait
    tourné une page, et les rapports institutionnels compteraient une lecture
    intégrale pour un simple coup d'œil.
    """
    assert PageAccessLog.objects.count() == 0

    client.get(manifest_path(session))

    assert PageAccessLog.objects.count() == 0


@pytest.mark.django_db
def test_a_page_without_tiles_is_left_out_rather_than_invented(client, session):
    """Une page traitée mais pas encore tuilée n'entre pas au manifeste.

    L'y faire figurer avec des dimensions par défaut décalerait tout le
    document, sans qu'aucune erreur ne le signale.
    """
    from document_ingestion.blob_storage import delete_prefix
    from document_ingestion.iiif import tiles_root

    page = DocumentPage.objects.get(version=session.version, page_number=2)
    delete_prefix(tiles_root(page))

    manifest = client.get(manifest_path(session)).json()

    numbers = [int(canvas["id"].rsplit("/", 1)[-1]) for canvas in manifest["items"]]
    assert numbers == [1, 3]


@pytest.mark.django_db
def test_an_expired_session_gets_no_manifest(client, session):
    ReaderSession.objects.filter(pk=session.pk).update(
        started_at=timezone.now() - timezone.timedelta(hours=2),
        expires_at=timezone.now() - timezone.timedelta(hours=1),
    )

    assert client.get(manifest_path(session)).status_code == 403


@pytest.mark.django_db
def test_the_manifest_never_names_a_stored_object(client, session):
    body = client.get(manifest_path(session)).content.decode()

    assert not re.search(r"storage|bucket|versions/|tiles/|\.pdf", body, re.I)


@pytest.mark.django_db
def test_it_is_never_cached_by_a_shared_intermediary(client, session):
    response = client.get(manifest_path(session))

    assert "private" in response["Cache-Control"]


@pytest.mark.django_db
def test_behind_a_proxy_the_manifest_announces_the_public_address(client, session, settings):
    """Le défaut le plus coûteux de cette architecture, s'il passait.

    Le visualiseur construit **toutes** ses requêtes à partir des adresses du
    manifeste. Derrière un proxy inverse, `build_absolute_uri` rend l'adresse
    interne du serveur : le manifeste s'affiche normalement et pas une seule
    image ne charge — le symptôme envoie alors la recherche du défaut vers le
    tuilage, qui n'y est pour rien.
    """
    settings.PUBLIC_API_BASE_URL = "https://bibliotheque.ga"

    manifest = client.get(manifest_path(session)).json()

    assert manifest["id"].startswith("https://bibliotheque.ga/api/v1/reader/sessions/")
    for canvas in manifest["items"]:
        service = canvas["items"][0]["items"][0]["body"]["service"][0]
        assert service["id"].startswith("https://bibliotheque.ga/")


@pytest.mark.django_db
def test_without_a_public_address_the_request_decides(client, session, settings):
    """Vide, le réglage ne doit pas casser l'accès direct ni le développement."""
    settings.PUBLIC_API_BASE_URL = ""

    manifest = client.get(manifest_path(session)).json()

    assert manifest["id"].startswith("http://testserver/api/v1/reader/sessions/")
