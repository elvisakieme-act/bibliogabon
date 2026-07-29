from django.contrib import admin
from django.urls import include, path

from config.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("reader/", include("document_reader.urls")),
    path("search/", include("search_discovery.urls")),
]
