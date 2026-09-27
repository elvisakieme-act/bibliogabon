"""Classes de permission DRF : de fines enveloppes sur les prédicats.

Aucune logique ici. La règle vit dans `accounts.permissions`, pour que
l'API, les services et l'admin posent la même question. Une classe qui
déciderait quoi que ce soit par elle-même créerait une seconde source de
vérité, et donc une divergence.

État du périmètre : la surface V1 est aujourd'hui orientée lecteur et ne
comporte aucun endpoint de gestion. Ces classes existent pour la tranche
« dépôt de contenu », qui en sera le premier consommateur réel. Les câbler
sur des endpoints publics qui n'en ont pas besoin ne ferait qu'ajouter du
bruit — et une permission posée au mauvais endroit se remarque moins
qu'une permission absente.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from accounts import permissions as roles


class IsContentAdmin(BasePermission):
    """Valider métadonnées, droits, statut et publication."""

    def has_permission(self, request, view) -> bool:
        return roles.can_review_publication(request.user)


class IsTeacherOrContentAdmin(BasePermission):
    """Déposer une ressource."""

    def has_permission(self, request, view) -> bool:
        return roles.can_submit_document(request.user)


class AdministersOrganization(BasePermission):
    """Agir sur une organisation précise.

    La portée se vérifie au niveau de l'objet : `has_permission` laisse
    passer tout utilisateur authentifié, et `has_object_permission`
    tranche une fois l'organisation connue. Une vue qui oublierait
    `check_object_permissions` n'obtiendrait donc aucune garantie de
    portée — c'est délibérément visible plutôt que silencieux.
    """

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        organization = getattr(obj, "organization", obj)
        return roles.administers_organization(request.user, organization)


class HasBackOfficeAccess(BasePermission):
    """Plancher de l'API staff : un lecteur n'y entre pas."""

    def has_permission(self, request, view) -> bool:
        return roles.has_back_office_access(request.user)
