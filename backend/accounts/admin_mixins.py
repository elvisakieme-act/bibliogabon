"""Autorité dans l'admin, dérivée des mêmes prédicats que l'API.

`is_staff` continue de décider si le site d'administration s'ouvre ; ces
mixins décident de ce qui y est utilisable. Un modérateur de contenu peut
ainsi valider une publication sans hériter de la facturation.
"""

from __future__ import annotations

from accounts import permissions as roles


class RolePermittedAdmin:
    """Dérive les cinq permissions d'admin d'un unique prédicat."""

    role_predicate = staticmethod(lambda user: False)

    def _allowed(self, request) -> bool:
        return bool(type(self).role_predicate(request.user))

    def has_module_permission(self, request):
        return self._allowed(request)

    def has_view_permission(self, request, obj=None):
        return self._allowed(request)

    def has_add_permission(self, request):
        return self._allowed(request)

    def has_change_permission(self, request, obj=None):
        return self._allowed(request)

    def has_delete_permission(self, request, obj=None):
        return self._allowed(request)


class ContentAdminArea(RolePermittedAdmin):
    """Catalogue, droits, modération : le périmètre du modérateur."""

    role_predicate = staticmethod(roles.is_content_admin)


class PlatformStaffArea(RolePermittedAdmin):
    """Facturation, comptes, rôles plateforme : super administrateur seul.

    « Un administrateur d'institution ne peut pas modifier les contrats,
    les tarifs globaux ni les rôles plateforme. » Un modérateur de contenu
    non plus.
    """

    role_predicate = staticmethod(roles.is_platform_staff)
