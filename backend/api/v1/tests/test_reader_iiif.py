"""Diffusion IIIF d'une page, sous session de lecture.

Le lecteur servait une image entière par page : reçue en totalité pour être
vue en petit, et impossible à zoomer au-delà de la largeur de rendu. Les
tuiles ne descendent que ce qui est regardé.

Deux invariants portent tout le reste :

- **L'autorisation n'est pas réécrite.** Texte, image entière et tuiles
  passent par la même `_authorized_page`. C'est le point où une seconde
  écriture ferait le plus de dégâts : une tuile livre le contenu.
- **La clé de stockage est reconstruite, jamais concaténée.** Un chemin reçu
  et recollé laisserait un `../` sortir de l'arborescence de la page.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
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
    # Petit exprès : le tuilage d'une page de 2480 px produit 54 objets, et la
    # suite n'a pas à les payer pour vérifier une règle d'accès.
    settings.DOCUMENT_PAGE_IMAGE_WIDTH = 600
    return tmp_path


def make_document(*, slug: str, access_model: str = Document.AccessModel.FREE) -> Document:
    domain = AcademicDomain.objects.create(name=f"D {slug}", slug=f"d-{slug}")
    document_type = DocumentType.objects.create(name=f"T {slug}", slug=f"t-{slug}")
    return Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
        published_at=timezone.now(),
    )


def tiled_session(document: Document) -> ReaderSession:
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


@pytest.fixture
def session(db, local_storage):
    return tiled_session(make_document(slug="tuiles-libres"))


def info_path(session: ReaderSession, page_number: int = 1) -> str:
    return reverse(
        "api-v1:reader-page-image-info",
        kwargs={"session_key": str(session.session_key), "page_number": page_number},
    )


def tile_path(
    session, region, size, page_number=1, rotation="0", quality="default", fmt="webp"
):
    return reverse(
        "api-v1:reader-page-tile",
        kwargs={
            "session_key": str(session.session_key),
            "page_number": page_number,
            "region": region,
            "size": size,
            "rotation": rotation,
            "quality": quality,
            "image_format": fmt,
        },
    )


# --- Le contrat entre le tuilage et l'écran --------------------------------


@pytest.mark.django_db
def test_info_json_describes_the_page(client, session):
    info = client.get(info_path(session)).json()

    assert info["profile"] == "level0"
    assert info["type"] == "ImageService3"
    assert info["width"] > 0 and info["height"] > 0
    assert info["tiles"][0]["scaleFactors"][0] == 1


@pytest.mark.django_db
def test_the_identifier_points_back_at_this_api_not_at_storage(client, session):
    """Le visualiseur construit ses adresses à partir de cet identifiant. S'il
    nommait un objet stocké, chaque tuile demandée trahirait l'emplacement du
    fichier."""
    info = client.get(info_path(session)).json()

    assert info["id"].endswith("/pages/1/iiif")
    assert not re.search(r"storage|bucket|versions/|\.webp", info["id"], re.I)


@pytest.mark.django_db
def test_every_declared_tile_is_actually_served(client, session):
    """L'invariant central du niveau 0 : un visualiseur ne demande que ce qui
    est déclaré. Une déclaration sans objet laisse la page vide au zoom, sans
    erreur serveur et sans trace dans les journaux."""
    from document_ingestion.iiif import plan_tiles

    info = client.get(info_path(session)).json()

    plans = plan_tiles(info["width"], info["height"], info["tiles"][0]["width"])
    assert plans
    for plan in plans:
        response = client.get(tile_path(session, plan.region, plan.size))
        assert response.status_code == 200, f"tuile déclarée mais refusée : {plan.region}"
        assert response["Content-Type"] == "image/webp"


@pytest.mark.django_db
def test_every_declared_size_is_actually_served(client, session):
    """Le défaut que seule l'exécution a révélé.

    `info.json` annonce des rendus de la page entière, et c'est la **première**
    image qu'un visualiseur demande pour sa vue d'ensemble. Ils étaient
    déclarés sans être produits : la page restait vide à l'ouverture, et le
    seul signe était un message dans la console du navigateur.

    Le test voisin vérifie les *tuiles*. Il ne disait rien des *tailles*, et
    c'est exactement par là que le défaut est passé.
    """
    info = client.get(info_path(session)).json()

    assert info["sizes"]
    for size in info["sizes"]:
        response = client.get(tile_path(session, "full", f"{size['width']},{size['height']}"))
        assert response.status_code == 200, f"taille déclarée mais refusée : {size}"


@pytest.mark.django_db
def test_the_full_size_image_is_served(client, session):
    response = client.get(tile_path(session, "full", "max"))

    assert response.status_code == 200
    assert len(b"".join(response.streaming_content)) > 0


# --- L'autorisation ---------------------------------------------------------


@pytest.mark.django_db
def test_an_expired_session_gets_no_tile(client, session):
    ReaderSession.objects.filter(pk=session.pk).update(
        started_at=timezone.now() - timezone.timedelta(hours=2),
        expires_at=timezone.now() - timezone.timedelta(hours=1),
    )

    assert client.get(tile_path(session, "full", "max")).status_code == 403
    assert client.get(info_path(session)).status_code == 403


@pytest.mark.django_db
def test_a_restricted_document_requires_an_entitlement(client, local_storage):
    from rest_framework.test import APIClient

    reader = User.objects.create_user(
        email="tuiles-sans-droit@bibliogabon.ga",
        password="passphrase",
        account_type=User.AccountType.INDIVIDUAL,
    )
    document = make_document(
        slug="tuiles-restreintes", access_model=Document.AccessModel.SUBSCRIPTION
    )
    session = tiled_session(document)
    session.user = reader
    session.save(update_fields=["user"])

    api = APIClient()
    api.force_authenticate(user=reader)

    assert api.get(tile_path(session, "full", "max")).status_code == 403
    assert api.get(info_path(session)).status_code == 403


@pytest.mark.django_db
def test_a_page_beyond_the_document_gets_nothing(client, session):
    assert client.get(tile_path(session, "full", "max", page_number=99)).status_code == 404


# --- La clé de stockage ne se concatène pas ---------------------------------


@pytest.mark.django_db
def test_a_traversal_attempt_is_refused_by_the_key_builder_itself(client, session):
    """C'est la fabrique de clés qui refuse, pas le stockage.

    Une première version de ce test passait pour la mauvaise raison :
    `FileSystemStorage` refuse un chemin qui remonte, et l'exception devenait
    un 404. Le backend S3 n'a pas ce garde-fou — la même requête y aurait été
    passée telle quelle. La barrière est donc dans `tile_storage_key`, qui
    valide chaque composante au lieu de les recoller.
    """
    from document_ingestion.iiif import UnknownTile, tile_storage_key

    for region, size in (("..", "max"), ("full", "../../.."), ("pct:10,10,10,10", "max")):
        with pytest.raises(UnknownTile):
            tile_storage_key("racine", region, size)

    for region in ("..", "%2e%2e"):
        response = client.get(
            f"/api/v1/reader/sessions/{session.session_key}/pages/1/iiif/"
            f"{region}/max/0/default.webp"
        )
        assert response.status_code == 404, region


@pytest.mark.django_db
def test_only_the_level_zero_rotation_and_quality_exist(client, session):
    """Les annoncer autrement ferait chercher au visualiseur un objet qui n'a
    jamais été produit."""
    assert client.get(tile_path(session, "full", "max", rotation="90")).status_code == 404
    assert client.get(tile_path(session, "full", "max", quality="gray")).status_code == 404
    assert client.get(tile_path(session, "full", "max", fmt="jpg")).status_code == 404


@pytest.mark.django_db
def test_an_undeclared_tile_is_a_404_not_a_server_error(client, session):
    response = client.get(tile_path(session, "9999,9999,512,512", "512,"))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- Le journal d'accès -----------------------------------------------------


@pytest.mark.django_db
def test_a_page_is_logged_once_however_many_tiles_are_fetched(client, session):
    """Afficher une page demande des dizaines de tuiles. Une ligne par tuile
    ferait du journal du bruit plutôt qu'une trace, et gonflerait d'autant les
    rapports institutionnels."""
    from document_ingestion.iiif import plan_tiles

    info = client.get(info_path(session)).json()
    for plan in plan_tiles(info["width"], info["height"], info["tiles"][0]["width"]):
        client.get(tile_path(session, plan.region, plan.size))

    assert PageAccessLog.objects.filter(session=session, page_number=1).count() == 1


@pytest.mark.django_db
def test_a_tile_is_never_cached_by_a_shared_intermediary(client, session):
    response = client.get(tile_path(session, "full", "max"))

    assert "private" in response["Cache-Control"]
    assert "public" not in response["Cache-Control"]


@pytest.mark.django_db
def test_the_response_never_carries_the_real_storage_key(client, session):
    from document_ingestion.iiif import tile_storage_key, tiles_root

    page = DocumentPage.objects.get(version=session.version, page_number=1)
    key = tile_storage_key(tiles_root(page), "full", "max")

    response = client.get(tile_path(session, "full", "max"))
    joined = " ".join(f"{k}: {v}" for k, v in response.items())

    assert key not in joined
    assert not re.search(r"storage|bucket|versions/|tiles/", joined, re.I), joined


@pytest.mark.django_db
def test_serving_many_tiles_writes_to_the_database_almost_never(client, session):
    """Le défaut que la capture a révélé, et que rien ne rendait visible.

    OpenSeadragon demande des dizaines de tuiles en parallèle pour une seule
    page. Chacune écrivait : une ligne de journal et un rafraîchissement de
    session. Observé comme « database is locked » sur SQLite — ce qui, sur
    PostgreSQL, aurait été une tempête d'écritures concurrentes, plus coûteuse
    et moins visible.

    Une page affichée doit donc coûter **une** écriture de journal, pas une
    par tuile.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from document_ingestion.iiif import plan_tiles

    info = client.get(info_path(session)).json()
    plans = plan_tiles(info["width"], info["height"], info["tiles"][0]["width"])
    assert len(plans) > 4, "il faut assez de tuiles pour que le test ait un sens"

    with CaptureQueriesContext(connection) as queries:
        for plan in plans:
            client.get(tile_path(session, plan.region, plan.size))

    writes = [
        q["sql"] for q in queries if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE"))
    ]
    assert len(writes) <= 2, (
        f"{len(writes)} écritures pour {len(plans)} tuiles : chaque tuile écrit en base"
    )


@pytest.mark.django_db
def test_the_one_row_per_page_rule_is_enforced_by_the_database(client, session):
    """Une règle tenue par le code seul cède à la première concurrence.

    Deux tuiles d'une page jamais lue peuvent arriver en même temps : le code
    vérifierait toutes deux qu'aucune ligne n'existe, puis en écrirait deux.
    """
    from django.db import IntegrityError, transaction

    client.get(tile_path(session, "full", "max"))
    existing = PageAccessLog.objects.get(session=session, page_number=1)

    # `bulk_create` court-circuite la validation du modèle : ce qui refuse
    # ici est la contrainte en base, et c'est elle qui compte — la validation
    # du modèle ne voit pas une écriture concurrente.
    with pytest.raises(IntegrityError), transaction.atomic():
        PageAccessLog.objects.bulk_create(
            [
                PageAccessLog(
                    session=session,
                    page=existing.page,
                    user=session.user,
                    document=session.document,
                    page_number=1,
                )
            ]
        )
