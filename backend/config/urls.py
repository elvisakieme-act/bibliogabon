from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("reader/", include("document_reader.urls")),
    path("search/", include("search_discovery.urls")),
]
