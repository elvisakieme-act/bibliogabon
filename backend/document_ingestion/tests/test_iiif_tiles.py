"""Tuilage IIIF d'une page.

Le lecteur servait une image entière par page : reçue en totalité pour être
vue en petit, et impossible à zoomer au-delà de la largeur de rendu. Le
tuilage inverse les deux.

L'invariant central n'est pas « des tuiles existent » mais **« ce que
`info.json` annonce existe »**. Un visualiseur ne demande que ce qui y est
déclaré : une taille ou un facteur d'échelle annoncé sans avoir été produit
laisse une page vide au zoom, sans erreur côté serveur et sans rien dans les
journaux.
"""

from __future__ import annotations

import json

import pytest
from PIL import Image

from catalog.models import AcademicDomain, Document, DocumentType
from document_ingestion.blob_storage import get_document_storage, open_stream
from document_ingestion.iiif import (
    TILE_SIZE,
    declared_sizes,
    image_info,
    plan_tiles,
    scale_factors,
    tile_storage_key,
    tiles_root,
    write_page_tiles,
)
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def page(db):
    domain = AcademicDomain.objects.create(name="Tuiles", slug="tuiles")
    document_type = DocumentType.objects.create(name="Cours", slug="cours-tuiles")
    document = Document.objects.create(
        title="Document tuilé",
        slug="document-tuile",
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )
    version = DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=1,
    )
    return DocumentPage.objects.create(
        version=version, page_number=1, status=DocumentPage.Status.PROCESSED
    )


def make_image(width: int, height: int) -> Image.Image:
    return Image.new("RGB", (width, height), (240, 240, 240))


# --- Le plan de tuilage -----------------------------------------------------


def test_scale_factors_go_until_the_page_fits_one_tile():
    """S'arrêter plus tôt laisserait un niveau de zoom sans tuiles : le
    visualiseur demanderait une image absente et la page resterait vide au
    dézoom complet."""
    factors = scale_factors(2480, 3508, TILE_SIZE)

    assert factors[0] == 1
    assert 3508 / factors[-1] <= TILE_SIZE
    assert 3508 / factors[-2] > TILE_SIZE, "un facteur de trop : du travail inutile"


def test_tiles_cover_the_whole_page_without_gap_or_overlap():
    """Un trou laisserait une bande blanche au milieu d'une page ; un
    recouvrement ferait télécharger deux fois la même zone."""
    width, height = 1000, 1400
    covered = [[0] * width for _ in range(height)]

    for plan in plan_tiles(width, height, TILE_SIZE):
        if plan.scale != 1:
            continue
        for y in range(plan.top, plan.top + plan.height):
            for x in range(plan.left, plan.left + plan.width):
                covered[y][x] += 1

    assert all(count == 1 for row in covered for count in row)


def test_edge_tiles_are_clipped_to_the_page():
    """Une région qui déborde ferait produire une tuile avec une bande vide,
    et l'Image API refuse une région hors de l'image."""
    width, height = 1000, 1400

    for plan in plan_tiles(width, height, TILE_SIZE):
        assert plan.left + plan.width <= width
        assert plan.top + plan.height <= height


# --- La promesse de `info.json` ---------------------------------------------


@pytest.mark.django_db
def test_every_declared_size_and_tile_actually_exists(page, local_storage):
    """L'invariant central. Un visualiseur ne demande que ce qui est déclaré :
    une déclaration sans objet produit une page vide au zoom, sans erreur
    serveur et sans trace dans les journaux."""
    image = make_image(1240, 1754)

    write_page_tiles(page, image)

    storage = get_document_storage()
    root = tiles_root(page)
    info = json.loads(open_stream(f"{root}/info.json").read())

    for plan in plan_tiles(info["width"], info["height"], info["tiles"][0]["width"]):
        key = tile_storage_key(root, plan.region, plan.size)
        assert storage.exists(key), f"tuile déclarée mais absente : {key}"


@pytest.mark.django_db
def test_every_declared_size_actually_exists(page, local_storage):
    """Le test qui manquait, et que seule l'exécution a révélé.

    `info.json` déclare des rendus de la page entière — 2480, 1240, 620, 310
    pour une A4 à 300 ppp. Un visualiseur s'en sert pour sa vue d'ensemble :
    c'est la **première** image qu'il demande. Les déclarer sans les produire
    laissait donc la page vide à l'ouverture, sans erreur côté serveur.

    Le test précédent vérifiait que chaque *tuile* déclarée existe. Il ne
    disait rien des *tailles*, et c'est exactement par là que le défaut est
    passé.
    """
    write_page_tiles(page, make_image(1240, 1754))

    storage = get_document_storage()
    root = tiles_root(page)
    info = json.loads(open_stream(f"{root}/info.json").read())

    assert info["sizes"], "info.json devrait annoncer des tailles"
    for size in info["sizes"]:
        key = tile_storage_key(root, "full", f"{size['width']},{size['height']}")
        assert storage.exists(key), f"taille déclarée mais absente : {key}"


@pytest.mark.django_db
def test_the_full_image_and_the_thumbnail_are_written(page, local_storage):
    """La première parce qu'un visualiseur la demande au dézoom complet, la
    seconde parce que le catalogue n'a aucune raison de télécharger une page
    de 300 ppp pour afficher une vignette."""
    write_page_tiles(page, make_image(1240, 1754))

    storage = get_document_storage()
    root = tiles_root(page)
    assert storage.exists(tile_storage_key(root, "full", "max"))
    smallest = declared_sizes(1240, 1754)[-1]
    assert storage.exists(
        tile_storage_key(root, "full", f"{smallest['width']},{smallest['height']}")
    )


@pytest.mark.django_db
def test_the_thumbnail_is_small_enough_to_be_a_thumbnail(page, local_storage):
    """Sans cette vérification, une vignette pourrait être l'image entière
    renommée — et une grille de vingt vignettes coûterait vingt pages."""
    result = write_page_tiles(page, make_image(2480, 3508))

    thumbnail = Image.open(open_stream(result.thumbnail.storage_key))

    assert thumbnail.width < 400
    assert thumbnail.width == declared_sizes(2480, 3508)[-1]["width"]


@pytest.mark.django_db
def test_a_reduced_tile_is_actually_reduced(page, local_storage):
    """Une tuile de facteur 2 doit faire la moitié de sa région. Rendre la
    région à sa taille d'origine ferait télécharger la pleine résolution à
    chaque niveau de zoom — l'inverse de ce que le tuilage apporte."""
    write_page_tiles(page, make_image(1240, 1754))

    root = tiles_root(page)
    reduced = [plan for plan in plan_tiles(1240, 1754, TILE_SIZE) if plan.scale == 2]
    assert reduced, "la page devrait avoir un niveau réduit"

    plan = reduced[0]
    tile = Image.open(open_stream(tile_storage_key(root, plan.region, plan.size)))
    assert tile.width == max(1, plan.width // 2)


def test_declared_sizes_match_the_scale_factors():
    info = image_info("x", 2480, 3508)
    factors = info["tiles"][0]["scaleFactors"]

    assert len(info["sizes"]) == len(factors)
    assert info["sizes"][0] == {"width": 2480, "height": 3508}
    assert info["profile"] == "level0"


# --- Les deux écritures d'une même taille -----------------------------------


def test_both_size_conventions_name_the_same_object():
    """L'Image API admet `l,` et `l,h` pour la même image.

    OpenSeadragon demande la seconde, d'autres clients la première. Ranger
    l'objet sous l'une laisserait l'autre en 404 — observé en vrai : le
    visualiseur demandait `108,366`, le stockage contenait `108,`, et rien ne
    s'affichait.
    """
    from document_ingestion.iiif import UnknownTile, canonical_size

    region = "2048,2048,432,1462"
    assert canonical_size(region, "108,366") == canonical_size(region, "108,")
    assert canonical_size(region, "max") == "max"

    # Une taille de page entière doit dire sa hauteur : la région `full` ne la
    # porte pas, donc rien ne permettrait de la déduire.
    with pytest.raises(UnknownTile):
        canonical_size("full", "310,")


@pytest.mark.django_db
def test_a_tile_can_be_asked_for_in_either_convention(page, local_storage):
    from document_ingestion.iiif import canonical_size

    write_page_tiles(page, make_image(1240, 1754))

    storage = get_document_storage()
    root = tiles_root(page)
    for plan in plan_tiles(1240, 1754, TILE_SIZE):
        width = plan.size.split(",")[0]
        short = f"{width},"
        assert canonical_size(plan.region, short) == plan.size
        assert storage.exists(tile_storage_key(root, plan.region, short))
