"""Parcourir le catalogue public : ce qu'on montre, et dans quel ordre.

Le point d'entrée du catalogue n'acceptait **aucun** paramètre : ni domaine,
ni langue, ni année, ni tri. Deux conséquences visibles. Le panneau de filtres
de l'écran renvoyait vers la recherche, donc on croyait filtrer une liste et
l'on changeait de page. Et l'accueil ne pouvait pas annoncer « entrés
récemment » : faute d'ordre, sa section s'intitulait « Quelques documents du
catalogue », ce qui était vrai mais pauvre.

Le filtrage vit ici plutôt que dans la vue, comme tout le reste du domaine, et
reste **séparé de celui de la recherche** : celle-ci interroge un index
dénormalisé et le classe par pertinence, celui-ci interroge les documents et
les classe par un critère demandé. Les réunir supposerait que « trouver » et
« parcourir » soient la même opération ; ils ne le sont pas, et l'index ne
porte pas le droit de lecture.
"""

from __future__ import annotations

from django.db.models import F

from catalog.models import Document

# Les ordres offerts, et eux seuls.
#
# Chacun se termine par un départage stable. Sans lui, deux documents publiés
# dans la même transaction — tout le jeu de démonstration l'est — sortent dans
# un ordre que PostgreSQL ne garantit pas d'une requête à l'autre : une même
# fiche peut alors apparaître sur deux pages successives, ou sur aucune.
ORDERINGS: dict[str, tuple] = {
    "title": ("title", "id"),
    # `nulls_last` : une date absente ne doit pas se présenter comme la plus
    # récente. Un document publié en a toujours une, mais une ligne ancienne
    # peut ne pas en avoir, et c'est précisément celle-là qui se glisserait en
    # tête de l'accueil.
    "-published_at": (F("published_at").desc(nulls_last=True), "-id"),
    "-publication_year": (
        F("publication_year").desc(nulls_last=True),
        "title",
        "id",
    ),
}
DEFAULT_ORDERING = "title"


class UnknownOrdering(ValueError):
    """Un ordre qui n'est pas offert.

    Refusé plutôt qu'ignoré : un paramètre silencieusement écarté est
    exactement ce qui faisait croire que le catalogue filtrait.
    """


def published_documents():
    """Les documents que le public peut voir, sans ordre imposé."""
    return (
        Document.objects.select_related(
            "academic_domain", "owner_organization", "document_type"
        )
        .filter(publication_status=Document.PublicationStatus.PUBLISHED)
        .exclude(access_model=Document.AccessModel.PRIVATE)
    )


def browse_documents(
    *,
    domain: str = "",
    language: str = "",
    access: str = "",
    document_type: str = "",
    year: int | None = None,
    ordering: str = DEFAULT_ORDERING,
):
    """Le catalogue public, filtré et ordonné.

    Un slug inconnu ne vaut pas erreur : il ne désigne simplement aucun
    document, et une liste vide est une réponse. Un *ordre* inconnu, lui, est
    une faute de contrat — ce n'est pas une valeur du fonds mais un mot-clé que
    l'on choisit dans une liste fermée.
    """
    if ordering not in ORDERINGS:
        raise UnknownOrdering(ordering)

    documents = published_documents()
    if domain:
        documents = documents.filter(academic_domain__slug=domain)
    if language:
        documents = documents.filter(language_code=language)
    if access:
        documents = documents.filter(access_model=access)
    if document_type:
        documents = documents.filter(document_type__slug=document_type)
    if year is not None:
        documents = documents.filter(publication_year=year)

    return documents.order_by(*ORDERINGS[ordering])
