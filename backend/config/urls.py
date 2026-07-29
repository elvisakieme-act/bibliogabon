from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path("api/v1/schema/", SpectacularAPIView.as_view(api_version="v1"), name="api-v1-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-v1-schema"), name="api-docs"),
    path("api/v1/", include("api.v1.urls")),
    path("admin/", admin.site.urls),
    path("reader/", include("document_reader.urls")),
    path("search/", include("search_discovery.urls")),
]
