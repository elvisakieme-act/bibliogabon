"""Socle de l'API staff.

Surface interne : elle montre délibérément ce que l'API publique cache —
brouillons, documents non publiés, états de traitement. Son contrat est
donc séparé, documenté dans son propre schéma, et fermé aux lecteurs.
"""

from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.permissions import HasBackOfficeAccess


class StaffAPIView(APIView):
    """Base de toute vue staff : impose le plancher d'autorisation.

    Hériter d'`APIView` directement laisserait la permission par défaut du
    projet, qui est `AllowAny`. Passer par cette base rend l'oubli
    impossible plutôt qu'improbable.
    """

    permission_classes = [HasBackOfficeAccess]


class StaffIndexView(StaffAPIView):
    @extend_schema(
        tags=["Staff"],
        summary="Staff API index",
        description="Entry point of the internal back-office API.",
        operation_id="staff_v1_index",
        responses={200: dict},
    )
    def get(self, request):
        return Response(
            {
                "name": "BiblioGABON staff API",
                "version": "v1",
                "schema": request.build_absolute_uri("schema/"),
                # L'écran de dépôt refuse un fichier hors bornes avant d'ouvrir
                # une requête, ce qui demande qu'il connaisse ces bornes. Les
                # recopier côté client les ferait dériver de la configuration
                # réelle : le serveur les annonce donc lui-même.
                "upload": {
                    "max_bytes": int(settings.DOCUMENT_UPLOAD_MAX_BYTES),
                    "accepted_mime_types": list(settings.DOCUMENT_UPLOAD_ACCEPTED_MIME_TYPES),
                },
            }
        )
