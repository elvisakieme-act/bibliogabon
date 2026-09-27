"""Périmètre du schéma OpenAPI public.

Le contrat public promet de ne jamais révéler l'existence d'un document
non publié. Générer son schéma depuis la configuration d'URL racine y
ferait entrer les chemins staff, qui existent justement pour les montrer.
"""

from django.urls import include, path


urlpatterns = [
    path("api/v1/", include("api.v1.urls")),
]
