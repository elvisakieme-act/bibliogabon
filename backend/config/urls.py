from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.health import health

urlpatterns = [
    path("health/", health, name="health"),
    # Chaque schéma est généré depuis son propre périmètre d'URL : sans
    # cela, le schéma public documenterait les chemins staff.
    path(
        "api/v1/schema/",
        SpectacularAPIView.as_view(api_version="v1", urlconf="config.schema_public"),
        name="api-v1-schema",
    ),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-v1-schema"), name="api-docs"),
    path("api/v1/", include("api.v1.urls")),
    path(
        "api/staff/v1/schema/",
        SpectacularAPIView.as_view(urlconf="config.schema_staff"),
        name="api-staff-v1-schema",
    ),
    path("api/staff/v1/", include("api.staff.v1.urls")),
    path("admin/", admin.site.urls),
    path("reader/", include("document_reader.urls")),
    path("search/", include("search_discovery.urls")),
]
