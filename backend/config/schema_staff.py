"""Périmètre du schéma OpenAPI interne."""

from django.urls import include, path

urlpatterns = [
    path("api/staff/v1/", include("api.staff.v1.urls")),
]
