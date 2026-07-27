from django.urls import path

from search_discovery import views


urlpatterns = [
    path("documents/", views.search_documents_view, name="search-documents"),
]
