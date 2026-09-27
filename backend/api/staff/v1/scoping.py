"""Ce que chaque acteur a le droit de voir dans le back-office.

La portée est appliquée sur le queryset, pas sur la vue de détail. Filtrer
seulement au détail laisserait fuiter l'existence d'un document par la
liste, par un compteur de pagination ou par un filtre — et l'existence
même d'un brouillon est une information.

Cette surface élargit délibérément la visibilité par rapport au catalogue
public, qui continue d'exclure brouillons, documents privés et retirés.
Les deux ne doivent jamais partager de queryset.
"""

from __future__ import annotations

from django.db.models import QuerySet

from accounts import permissions as roles
from catalog.models import Document


def documents_visible_to(user) -> QuerySet[Document]:
    """Documents qu'un acteur peut manipuler depuis le back-office.

    - modérateur de contenu et super administrateur : tous les états ;
    - enseignant-auteur : ceux dont il est auteur ou co-auteur, tous états ;
    - toute autre personne, y compris un lecteur authentifié : aucun.
    """
    base = Document.objects.select_related(
        "academic_domain", "document_type", "owner_organization"
    )

    if roles.is_content_admin(user):
        return base

    if not roles.is_teacher_author(user):
        return base.none()

    # `distinct()` : un auteur rattaché deux fois (auteur puis co-auteur)
    # dédoublerait la ligne au travers de la jointure.
    return base.filter(document_authors__author__linked_user=user).distinct()
