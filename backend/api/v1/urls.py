from django.urls import path

from api.v1.auth import (
    CurrentUserView,
    DocumentedTokenObtainPairView,
    DocumentedTokenRefreshView,
    LogoutView,
    RegisterView,
)
from api.v1.catalog import AuthorListView, DocumentDetailView, DocumentListView, DomainListView, SearchView
from api.v1.reader import ReaderPageView, ReaderSessionCreateView, ReaderSessionDeleteView
from api.v1.user_library import (
    FavoriteDeleteView,
    FavoriteListCreateView,
    ReadingProgressListView,
    ReadingProgressUpdateView,
)
from api.v1.views import api_index

app_name = "api-v1"

urlpatterns = [
    path("", api_index, name="index"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/token/", DocumentedTokenObtainPairView.as_view(), name="token-obtain"),
    path("auth/token/refresh/", DocumentedTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("me/favorites/", FavoriteListCreateView.as_view(), name="favorite-list-create"),
    path("me/favorites/<int:document_id>/", FavoriteDeleteView.as_view(), name="favorite-delete"),
    path("me/reading-progress/", ReadingProgressListView.as_view(), name="reading-progress-list"),
    path(
        "me/reading-progress/<int:document_id>/",
        ReadingProgressUpdateView.as_view(),
        name="reading-progress-update",
    ),
    path("catalog/documents/", DocumentListView.as_view(), name="catalog-documents"),
    path(
        "catalog/documents/<int:document_id>/",
        DocumentDetailView.as_view(),
        name="catalog-document-detail",
    ),
    path("catalog/domains/", DomainListView.as_view(), name="catalog-domains"),
    path("catalog/authors/", AuthorListView.as_view(), name="catalog-authors"),
    path("search/", SearchView.as_view(), name="search"),
    path("reader/sessions/", ReaderSessionCreateView.as_view(), name="reader-session-create"),
    path(
        "reader/sessions/<uuid:session_key>/pages/<int:page_number>/",
        ReaderPageView.as_view(),
        name="reader-page",
    ),
    path(
        "reader/sessions/<uuid:session_key>/",
        ReaderSessionDeleteView.as_view(),
        name="reader-session-delete",
    ),
]
