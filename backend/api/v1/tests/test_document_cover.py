"""Couverture d'un document.

Le catalogue n'avait aucune couverture : `Document` n'a pas de champ, et l'API
renvoyait `"cover": None` codé en dur à trois endroits. Onze documents, onze
rectangles dégradés — une bibliothèque sans couvertures est grise par
construction, et aucune palette ne rattrape cela.

L'image de la page 1 est pourtant produite à chaque ingestion et n'était jamais
consommée. Elle devient la couverture.

La règle d'exposition est celle que le produit tient depuis le début, et elle
n'est pas réinventée ici : **un document découvrable a une couverture, un
document non découvrable n'en a pas.** C'est `document_is_reader_accessible`,
donc une seule représentation de la règle plutôt que deux qui divergeront.

Et l'invariant tient : la clé de stockage ne sort jamais. L'image est diffusée
par un point d'accès opaque, jamais par une adresse d'objet.
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
    settings.DOCUMENT_PAGE_IMAGE_WIDTH = 480
    return tmp_path


def make_document(
    *,
    slug: str,
    status: str = Document.PublicationStatus.PUBLISHED,
    access_model: str = Document.AccessModel.FREE,
) -> Document:
    domain = AcademicDomain.objects.create(name=f"D {slug}", slug=f"d-{slug}")
    document_type = DocumentType.objects.create(name=f"T {slug}", slug=f"t-{slug}")
    return Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=status,
        published_at=timezone.now() if status == Document.PublicationStatus.PUBLISHED else None,
    )


def ingest_with_cover(document: Document):
    """Ingère le PDF et rend la première page, comme le fait la chaîne Celery."""
    with FIXTURE.open("rb") as handle:
        version = ingest_document_file(
            document=document, fileobj=handle, original_filename="s.pdf"
        )
    first = DocumentPage.objects.get(version=version, page_number=1)
    tasks.render_page_image.apply(args=[first.pk]).get()
    return version


def cover_path(document: Document) -> str:
    return reverse("api-v1:catalog-document-cover", kwargs={"document_id": document.pk})


# --- Ce qui a une couverture ------------------------------------------------


@pytest.mark.django_db
def test_a_published_free_document_serves_its_first_page(client, local_storage):
    document = make_document(slug="couverture-libre")
    ingest_with_cover(document)

    response = client.get(cover_path(document))

    assert response.status_code == 200
    assert response["Content-Type"] == "image/webp"
    assert len(b"".join(response.streaming_content)) > 0


@pytest.mark.django_db
def test_a_restricted_but_discoverable_document_also_has_a_cover(client, local_storage):
    """Une librairie montre la couverture d'un livre qu'on n'a pas acheté. Sans
    cela, la moitié du catalogue resterait grise et le classement par accès
    deviendrait un classement par laideur."""
    document = make_document(
        slug="couverture-abonnement", access_model=Document.AccessModel.SUBSCRIPTION
    )
    ingest_with_cover(document)

    assert client.get(cover_path(document)).status_code == 200


@pytest.mark.django_db
def test_the_catalogue_payload_carries_the_cover_url(client, local_storage):
    document = make_document(slug="couverture-dans-la-charge")
    ingest_with_cover(document)

    payload = client.get(
        reverse("api-v1:catalog-document-detail", kwargs={"document_id": document.pk})
    ).json()

    assert payload["cover"] == cover_path(document)


# --- Ce qui n'en a pas ------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        Document.PublicationStatus.DRAFT,
        Document.PublicationStatus.SUBMITTED,
        Document.PublicationStatus.REJECTED,
        Document.PublicationStatus.WITHDRAWN,
        Document.PublicationStatus.ARCHIVED,
    ],
)
def test_a_document_that_is_not_published_has_no_cover(client, local_storage, status):
    """Servir la page 1 d'un brouillon confirmerait son existence et livrerait
    son contenu — deux fuites en un seul geste."""
    document = make_document(slug=f"couverture-{status}", status=status)
    ingest_with_cover(document)

    assert client.get(cover_path(document)).status_code == 404


@pytest.mark.django_db
def test_a_private_document_has_no_cover(client, local_storage):
    document = make_document(
        slug="couverture-privee", access_model=Document.AccessModel.PRIVATE
    )
    ingest_with_cover(document)

    assert client.get(cover_path(document)).status_code == 404


@pytest.mark.django_db
def test_a_document_without_a_rendered_page_has_no_cover(client, local_storage):
    """Un document du catalogue dont le fichier n'est pas encore traité : pas
    de couverture, et surtout pas d'erreur serveur."""
    document = make_document(slug="couverture-absente")

    response = client.get(cover_path(document))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_an_unknown_document_has_no_cover(client):
    response = client.get(
        reverse("api-v1:catalog-document-cover", kwargs={"document_id": 999999})
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_document_without_a_cover_reports_null(client, local_storage):
    document = make_document(slug="couverture-nulle")

    payload = client.get(
        reverse("api-v1:catalog-document-detail", kwargs={"document_id": document.pk})
    ).json()

    assert payload["cover"] is None


# --- L'invariant de confidentialité ----------------------------------------


@pytest.mark.django_db
def test_the_cover_url_never_names_a_stored_object(client, local_storage):
    """L'adresse de la couverture est opaque. Elle ne doit ni contenir de clé
    de stockage, ni révéler le format ou l'emplacement de l'objet."""
    document = make_document(slug="couverture-opaque")
    ingest_with_cover(document)

    for path in (
        reverse("api-v1:catalog-documents"),
        reverse("api-v1:catalog-document-detail", kwargs={"document_id": document.pk}),
        reverse("api-v1:search"),
    ):
        body = client.get(path).content.decode()
        assert not re.search(r"\.webp|\.pdf|storage|bucket|versions/", body, re.I), path


@pytest.mark.django_db
def test_the_cover_response_never_carries_the_real_storage_key(client, local_storage):
    """La forme la plus forte du test : on compare aux **vraies** valeurs de
    l'objet stocké, pas à un motif approchant.

    Une première version cherchait la sous-chaîne « .webp », et attrapait le
    nom de téléchargement que nous choisissons nous-mêmes — un test faux, qui
    aurait poussé à retirer une information légitime plutôt qu'à tenir la
    règle.
    """
    from api.v1.covers import find_cover_asset

    document = make_document(slug="couverture-entetes")
    ingest_with_cover(document)
    asset = find_cover_asset(document)

    response = client.get(cover_path(document))
    joined = " ".join(f"{k}: {v}" for k, v in response.items())

    assert asset.storage_key not in joined
    assert asset.storage_bucket not in joined or not asset.storage_bucket
    assert not re.search(r"storage|bucket|versions/", joined, re.I), joined


# --- La recherche aussi -----------------------------------------------------


@pytest.mark.django_db
def test_search_results_carry_the_cover(client, local_storage):
    """La recherche a son propre sérialiseur, pas celui du catalogue.

    Croire à un « point d'appel unique » suffisait à laisser l'écran de
    résultats entièrement gris alors que le catalogue affichait ses
    couvertures. Le test précédent sur l'opacité des adresses passait sur
    `/search/` pour la mauvaise raison : il n'y avait aucune couverture à y
    trouver.
    """
    document = make_document(slug="couverture-recherche")
    ingest_with_cover(document)

    results = client.get(reverse("api-v1:search"), {"q": "Document"}).json()["results"]

    found = [r for r in results if r["id"] == document.pk]
    assert found, "le document ingéré devrait remonter dans la recherche"
    assert found[0]["cover"] == cover_path(document)


@pytest.mark.django_db
def test_search_resolves_covers_in_a_constant_number_of_queries(client, local_storage):
    """Le coût ne doit pas grandir avec le nombre de résultats affichés."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    for index in range(2):
        ingest_with_cover(make_document(slug=f"recherche-peu-{index}"))
    with CaptureQueriesContext(connection) as few:
        assert client.get(reverse("api-v1:search"), {"q": "Document"}).status_code == 200

    for index in range(6):
        ingest_with_cover(make_document(slug=f"recherche-plus-{index}"))
    with CaptureQueriesContext(connection) as many:
        response = client.get(reverse("api-v1:search"), {"q": "Document"})
    assert response.json()["count"] == 8

    assert len(many) == len(few), (
        f"le coût grandit avec les résultats : {len(few)} requêtes pour 2, {len(many)} pour 8"
    )


@pytest.mark.django_db
def test_a_search_result_without_a_rendered_page_reports_null(client, local_storage):
    """Un document indexé mais dont la page 1 n'est pas rendue.

    Fabriquer l'adresse pour tout résultat passait tous les autres tests : la
    recherche ne renvoie que des documents découvrables, donc la condition
    semblait toujours vraie. Elle ne l'est pas — un document peut être publié
    et indexé sans que son image de page existe, et l'écran afficherait alors
    une vignette brisée.
    """
    from search_discovery.services import rebuild_document_search_index

    document = make_document(slug="recherche-sans-image")
    rebuild_document_search_index(document)

    results = client.get(reverse("api-v1:search"), {"q": "Document"}).json()["results"]

    found = [r for r in results if r["id"] == document.pk]
    assert found, "le document devrait être indexé"
    assert found[0]["cover"] is None
