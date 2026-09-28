"""Couverture d'un document.

Le catalogue n'en avait aucune : `Document` n'a pas de champ de couverture, et
l'API renvoyait `"cover": None` codé en dur. Onze documents, onze rectangles
dégradés — une bibliothèque sans couvertures est grise par construction.

L'image de la page 1 est pourtant produite à chaque ingestion et n'était jamais
consommée. Elle devient la couverture.

Deux invariants sont tenus ici, et aucun n'est nouveau :

- **La règle d'exposition n'est pas réinventée.** Un document découvrable a une
  couverture, un document non découvrable n'en a pas, et « découvrable » est
  `document_is_reader_accessible` — la même fonction que le lecteur. Deux
  représentations d'une même règle finissent toujours par diverger.

- **La clé de stockage ne sort jamais.** L'image est diffusée par ce point
  d'accès, dont l'adresse ne dit ni le format, ni l'emplacement, ni le nom de
  l'objet. Ce que le produit promet depuis le premier jour vaut aussi pour une
  vignette.
"""

from __future__ import annotations

from django.http import FileResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from api.v1.errors import error_response
from catalog.models import Document
from document_ingestion.blob_storage import open_stream
from document_ingestion.models import DocumentAsset, DocumentVersion
from document_reader.services import document_is_reader_accessible

# Durée de cache d'une couverture. Elle ne change qu'à une réingestion, et un
# navigateur qui la redemande à chaque vignette de catalogue paierait un aller
# -retour par document affiché.
COVER_MAX_AGE_SECONDS = 60 * 60 * 24


# La vignette d'abord, la page entière ensuite. Le tuilage produit les deux :
# une grille de vingt couvertures ne doit pas coûter vingt pages à 300 ppp,
# et un document tuilé avant que la vignette existe doit rester affichable.
COVER_ASSET_PREFERENCE = (
    DocumentAsset.AssetType.COVER,
    DocumentAsset.AssetType.PAGE_IMAGE,
)


def find_cover_asset(document: Document) -> DocumentAsset | None:
    version = (
        DocumentVersion.objects.filter(
            document=document,
            is_current=True,
            status=DocumentVersion.Status.PROCESSED,
        )
        .order_by("-created_at")
        .first()
    )
    if version is None:
        return None
    for asset_type in COVER_ASSET_PREFERENCE:
        asset = (
            DocumentAsset.objects.filter(
                version=version, asset_type=asset_type, page__page_number=1
            )
            .order_by("id")
            .first()
        )
        if asset is not None:
            return asset
    return None


def documents_with_cover(documents) -> set[int]:
    """Identifiants des documents qui ont une couverture, en une requête.

    Compagnon groupé de `cover_url_for`, sur le modèle de
    `readable_document_ids_for_user` : sans lui, sérialiser une page de
    catalogue coûterait deux requêtes par document, et le coût grandirait avec
    la liste. Deux tests de coût constant existaient déjà pour attraper
    exactement cela — ils l'ont attrapé.
    """
    documents = list(documents)
    discoverable = [d.pk for d in documents if document_is_reader_accessible(d)]
    if not discoverable:
        return set()
    return set(
        DocumentAsset.objects.filter(
            version__document_id__in=discoverable,
            version__is_current=True,
            version__status=DocumentVersion.Status.PROCESSED,
            asset_type__in=COVER_ASSET_PREFERENCE,
            page__page_number=1,
        ).values_list("version__document_id", flat=True)
    )


def cover_url_for(
    document: Document, document_ids_with_cover: set[int] | None = None
) -> str | None:
    """Adresse de la couverture, ou `None` si le document n'en a pas.

    Appelée par les sérialiseurs du catalogue. Le calcul reste volontairement
    ici : un sérialiseur qui fabriquerait l'adresse lui-même oublierait un jour
    la condition de découvrabilité.
    """
    if not document_is_reader_accessible(document):
        return None
    if document_ids_with_cover is None:
        if find_cover_asset(document) is None:
            return None
    elif document.pk not in document_ids_with_cover:
        return None
    return f"/api/v1/catalog/documents/{document.pk}/cover/"


class DocumentCoverView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Catalog"],
        summary="Serve the cover image of a discoverable document",
        description=(
            "The rendered first page, streamed through an opaque path. A "
            "document that is not discoverable returns 404, never 403: "
            "answering 'forbidden' would confirm a draft exists. No storage "
            "key, bucket or object name ever appears in the URL or the headers."
        ),
        operation_id="v1_document_cover",
        responses={
            200: OpenApiResponse(description="WebP image"),
            404: OpenApiResponse(description="No discoverable cover"),
        },
    )
    def get(self, request, document_id: int):
        document = Document.objects.filter(pk=document_id).first()
        if document is None or not document_is_reader_accessible(document):
            return error_response("not_found", "Document introuvable.", 404)

        asset = find_cover_asset(document)
        if asset is None:
            # Un document du catalogue dont le fichier n'est pas encore traité :
            # pas de couverture, et surtout pas d'erreur serveur.
            return error_response("not_found", "Ce document n'a pas de couverture.", 404)

        response = FileResponse(
            open_stream(asset.storage_key),
            content_type=asset.mime_type or "image/webp",
        )
        # `FileResponse` nomme le fichier téléchargé d'après le flux, ce qui
        # ferait apparaître la clé de stockage dans un en-tête. On impose donc
        # le nôtre.
        response.headers["Content-Disposition"] = (
            f'inline; filename="couverture-{document.pk}.webp"'
        )
        response.headers["Cache-Control"] = f"public, max-age={COVER_MAX_AGE_SECONDS}"
        return response
