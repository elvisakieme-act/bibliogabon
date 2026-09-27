"""Recherche d'auteurs, pour rattacher un contributeur à un document.

L'endpoint public `/api/v1/catalog/authors/` ne liste que les auteurs de
documents *publiés* : un déposant n'y trouverait donc jamais un co-auteur
qui n'a pas encore paru, ce qui est précisément le cas au moment du dépôt.
Cette vue voit tout le registre.

Lecture seule, et délibérément : créer un auteur touche au registre national
des contributeurs, ce qui pose des questions de doublons et d'autorité que le
back-office devra trancher explicitement. En attendant, un auteur absent se
signale à l'écran plutôt que d'être inventé par le premier déposant.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema

from api.staff.v1.views import StaffAPIView
from api.v1.pagination import StandardResultsSetPagination
from catalog.models import Author


class StaffAuthorListView(StaffAPIView):
    @extend_schema(
        tags=["Staff documents"],
        summary="Search the author registry",
        description=(
            "Every author, published or not, so a depositor can attach a "
            "co-author who has never appeared in the catalogue. Exposes only "
            "identity: name, type and affiliation."
        ),
        operation_id="staff_v1_authors_list",
        parameters=[OpenApiParameter("q", str, description="Name fragment")],
    )
    def get(self, request):
        authors = Author.objects.all()
        if value := request.query_params.get("q"):
            authors = authors.filter(display_name__icontains=value)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(
            authors.order_by("normalized_name", "display_name", "id"), request, view=self
        )
        return paginator.get_paginated_response(
            [
                {
                    "id": author.pk,
                    "display_name": author.display_name,
                    "author_type": author.author_type,
                    "affiliation": author.affiliation,
                }
                for author in page
            ]
        )
