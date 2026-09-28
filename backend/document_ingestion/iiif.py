"""Tuilage IIIF d'une page, au niveau 0 de l'Image API.

Le lecteur servait une image entière par page : un lecteur la recevait en
totalité pour la voir en petit, et ne pouvait pas zoomer au-delà de la
résolution choisie. Le tuilage inverse les deux : il ne descend que ce qui est
regardé, et permet un zoom que la largeur de rendu ne borne plus.

**Niveau 0, tuiles pré-calculées.** L'Image API accepte un serveur d'images qui
recadre à la demande (niveau 2) ou un jeu d'objets figés que `info.json`
déclare (niveau 0). Le niveau 0 évite d'ajouter un service à exploiter — une
JVM de plus — à une équipe qui vient de choisir l'auto-hébergement. Il se paie
en objets : mesuré à 54 par page à 300 ppp, contre un seul aujourd'hui.

Les clés reproduisent exactement la forme des URL de l'Image API,
`{région}/{taille}/{rotation}/{qualité}.{format}`, pour que servir une tuile
soit une correspondance directe et non une traduction — une traduction finirait
par diverger de ce que `info.json` annonce.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass

from django.conf import settings

from document_ingestion.blob_storage import save_stream
from document_processing.models import DocumentPage

# 300 ppp pour une A4 : la norme d'archivage pour du texte. Le tuilage rend ce
# choix peu coûteux pour le lecteur, qui ne télécharge que ce qu'il regarde —
# mesuré à 249 ko par page stockés, contre ~40 ko téléchargés pour voir une
# page entière aujourd'hui.
DEFAULT_TILE_WIDTH = 2480
TILE_SIZE = 512
THUMBNAIL_WIDTH = 200
WEBP_QUALITY = 80


@dataclass(frozen=True)
class StoredObject:
    """Ce qu'un `DocumentAsset` a besoin de savoir d'un objet écrit."""

    storage_key: str
    byte_size: int
    checksum_sha256: str


@dataclass(frozen=True)
class TilingResult:
    """Résultat d'un tuilage : le `info.json`, et les deux objets référencés.

    Seuls l'image entière et la vignette ont une ligne en base — la première
    sert de repli au lecteur, la seconde de couverture au catalogue. Les
    dizaines de tuiles n'en ont aucune : leurs clés sont déterministes, et
    leur donner une ligne chacune paierait en lignes une question de stockage.
    """

    info: dict
    full: StoredObject
    thumbnail: StoredObject


@dataclass(frozen=True)
class TilePlan:
    """Une tuile à produire : la région source et la taille rendue."""

    region: str
    size: str
    left: int
    top: int
    width: int
    height: int
    scale: int


def tiles_root(page: DocumentPage) -> str:
    prefix = getattr(settings, "DOCUMENT_STORAGE_KEY_PREFIX", "documents")
    return (
        f"{prefix}/{page.version.document_id}/versions/"
        f"{page.version.version_label}/pages/{page.page_number:04d}/tiles"
    )


# Les seules formes que le niveau 0 produit. La validation est ici, dans la
# fabrique de clés, et non chez l'appelant : un appelant qui l'oublierait
# recollerait un chemin reçu, et un « .. » sortirait de l'arborescence de la
# page. `FileSystemStorage` refuse ce cas de lui-même ; le backend S3, non.
REGION_PATTERN = re.compile(r"^(full|\d+,\d+,\d+,\d+)$")
SIZE_PATTERN = re.compile(r"^(max|\d+,|\d+,\d+)$")


class UnknownTile(ValueError):
    """Région ou taille qui n'existe pas au niveau 0."""


def canonical_size(region: str, size: str) -> str:
    """Forme canonique d'une taille : toujours `largeur,hauteur`.

    L'Image API admet `l,` et `l,h` pour la même image — la hauteur est
    déduite. OpenSeadragon demande la seconde forme, d'autres clients la
    première, et ranger l'objet sous l'une laisserait l'autre en 404.
    Observé en vrai : le visualiseur demandait `108,366`, le stockage
    contenait `108,`, et rien ne s'affichait.

    La hauteur manquante se déduit de la région, qui la porte toujours : une
    tuile de région `x,y,l,h` réduite à la largeur `w` fait `h * w / l`.
    """
    if size == "max":
        return size
    width_text, _, height_text = size.partition(",")
    if height_text:
        return size
    if region == "full":
        raise UnknownTile("a full-page size must state its height")
    _, _, region_width, region_height = (int(value) for value in region.split(","))
    width = int(width_text)
    return f"{width},{max(1, round(region_height * width / region_width))}"


def tile_storage_key(root: str, region: str, size: str) -> str:
    """Clé d'une tuile, calquée sur la forme des URL de l'Image API.

    Les composantes sont validées, pas concaténées telles quelles : c'est la
    seule barrière entre un chemin reçu d'un client et l'arborescence privée
    d'un document.
    """
    if not REGION_PATTERN.match(region):
        raise UnknownTile(f"region {region!r} does not exist at level 0")
    if not SIZE_PATTERN.match(size):
        raise UnknownTile(f"size {size!r} does not exist at level 0")
    return f"{root}/{region}/{canonical_size(region, size)}/0/default.webp"


def scale_factors(width: int, height: int, tile: int = TILE_SIZE) -> list[int]:
    """Facteurs d'échelle, jusqu'à ce que la page entière tienne dans une tuile.

    S'arrêter plus tôt laisserait un niveau de zoom sans tuiles : le
    visualiseur demanderait alors une image qui n'existe pas, et la page
    resterait vide au dézoom.
    """
    factors, factor = [1], 1
    while width / factor > tile or height / factor > tile:
        factor *= 2
        factors.append(factor)
    return factors


def plan_tiles(width: int, height: int, tile: int = TILE_SIZE) -> list[TilePlan]:
    """Toutes les tuiles qu'un visualiseur peut demander pour cette page."""
    plans = []
    for scale in scale_factors(width, height, tile):
        region_size = tile * scale
        for top in range(0, height, region_size):
            for left in range(0, width, region_size):
                region_width = min(region_size, width - left)
                region_height = min(region_size, height - top)
                plans.append(
                    TilePlan(
                        region=f"{left},{top},{region_width},{region_height}",
                        # Forme canonique `largeur,hauteur` : les clients
                        # demandent l'une ou l'autre écriture, et `canonical_size`
                        # les ramène toutes deux ici.
                        size=(
                            f"{max(1, round(region_width / scale))},"
                            f"{max(1, round(region_height / scale))}"
                        ),
                        left=left,
                        top=top,
                        width=region_width,
                        height=region_height,
                        scale=scale,
                    )
                )
    return plans


def declared_sizes(width: int, height: int, tile: int = TILE_SIZE) -> list[dict]:
    """Rendus de la page entière que `info.json` annonce.

    Un visualiseur s'en sert pour sa vue d'ensemble — c'est la première image
    qu'il demande. Les déclarer sans les produire laisse donc la page vide à
    l'ouverture, ce qui est le pire moment.
    """
    return [
        {"width": max(1, round(width / factor)), "height": max(1, round(height / factor))}
        for factor in scale_factors(width, height, tile)
    ]


def image_info(identifier: str, width: int, height: int, tile: int = TILE_SIZE) -> dict:
    """`info.json` de l'Image API 3.0, niveau 0.

    Le visualiseur ne demande que ce qui est déclaré ici. Déclarer une taille
    ou un facteur d'échelle qui n'a pas été produit ferait chercher au lecteur
    une tuile absente.
    """
    return {
        "@context": "http://iiif.io/api/image/3/context.json",
        "id": identifier,
        "type": "ImageService3",
        "protocol": "http://iiif.io/api/image",
        "profile": "level0",
        "width": width,
        "height": height,
        "tiles": [{"width": tile, "scaleFactors": scale_factors(width, height, tile)}],
        "sizes": declared_sizes(width, height, tile),
        "extraFormats": ["webp"],
        "preferredFormats": ["webp"],
    }


def encode_webp(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=WEBP_QUALITY, method=4)
    return buffer.getvalue()


def _store(storage_key: str, payload: bytes) -> StoredObject:
    save_stream(storage_key, io.BytesIO(payload))
    return StoredObject(
        storage_key=storage_key,
        byte_size=len(payload),
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
    )


def write_page_tiles(page: DocumentPage, image, *, tile: int = TILE_SIZE) -> TilingResult:
    """Produit et range toutes les tuiles d'une page. Renvoie son `info.json`.

    L'image entière et une vignette sont écrites avec les tuiles : la première
    parce qu'un visualiseur la demande au dézoom complet, la seconde parce que
    le catalogue affiche des vignettes et n'a aucune raison d'y télécharger une
    page de 300 ppp.
    """
    from PIL import Image

    width, height = image.size
    root = tiles_root(page)

    for plan in plan_tiles(width, height, tile):
        crop = image.crop((plan.left, plan.top, plan.left + plan.width, plan.top + plan.height))
        if plan.scale > 1:
            crop = crop.resize(
                (max(1, plan.width // plan.scale), max(1, plan.height // plan.scale)),
                Image.LANCZOS,
            )
        _store(tile_storage_key(root, plan.region, plan.size), encode_webp(crop))

    full = _store(tile_storage_key(root, "full", "max"), encode_webp(image))

    # Chaque taille annoncée doit exister. Une version antérieure les
    # déclarait sans les produire : le visualiseur demandait sa vue d'ensemble
    # et ne recevait rien, donc la page restait vide à l'ouverture — au pire
    # moment possible, et sans erreur côté serveur.
    sizes = declared_sizes(width, height, tile)
    stored_sizes = [
        _store(
            tile_storage_key(root, "full", f"{size['width']},{size['height']}"),
            encode_webp(
                image
                if size["width"] == width
                else image.resize((size["width"], size["height"]), Image.LANCZOS)
            ),
        )
        for size in sizes
    ]
    # La couverture du catalogue est la plus petite taille annoncée : pas
    # d'objet supplémentaire, et rien qui ne soit pas déclaré.
    thumbnail = stored_sizes[-1]

    info = image_info(identifier="", width=width, height=height, tile=tile)
    _store(f"{root}/info.json", json.dumps(info).encode("utf-8"))
    return TilingResult(info=info, full=full, thumbnail=thumbnail)
