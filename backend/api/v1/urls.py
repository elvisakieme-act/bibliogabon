from django.urls import path

from api.v1.auth import (
    CurrentUserView,
    DocumentedTokenObtainPairView,
    DocumentedTokenRefreshView,
    LogoutView,
    RegisterView,
)
from api.v1.catalog import (
    AuthorListView,
    DocumentDetailView,
    DocumentListView,
    DocumentTypeListView,
    DomainListView,
    SearchView,
)
from api.v1.covers import DocumentCoverView
from api.v1.reader import (
    ReaderManifestView,
    ReaderPageImageInfoView,
    ReaderPageImageView,
    ReaderPageTileView,
    ReaderPageView,
    ReaderSessionCreateView,
    ReaderSessionDeleteView,
)
from api.v1.reports import DocumentReportView, DocumentWithdrawalRequestView
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
    path(
        "me/favorites/<int:document_id>/", FavoriteDeleteView.as_view(), name="favorite-delete"
    ),
    path(
        "me/reading-progress/", ReadingProgressListView.as_view(), name="reading-progress-list"
    ),
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
    path(
        "catalog/documents/<int:document_id>/cover/",
        DocumentCoverView.as_view(),
        name="catalog-document-cover",
    ),
    path("catalog/domains/", DomainListView.as_view(), name="catalog-domains"),
    path("catalog/types/", DocumentTypeListView.as_view(), name="catalog-types"),
    path("catalog/authors/", AuthorListView.as_view(), name="catalog-authors"),
    path(
        "documents/<int:document_id>/report/",
        DocumentReportView.as_view(),
        name="document-report",
    ),
    path(
        "documents/<int:document_id>/withdrawal-request/",
        DocumentWithdrawalRequestView.as_view(),
        name="document-withdrawal-request",
    ),
    path("search/", SearchView.as_view(), name="search"),
    path("reader/sessions/", ReaderSessionCreateView.as_view(), name="reader-session-create"),
    path(
        "reader/sessions/<uuid:session_key>/pages/<int:page_number>/",
        ReaderPageView.as_view(),
        name="reader-page",
    ),
    path(
        "reader/sessions/<uuid:session_key>/pages/<int:page_number>/image/",
        ReaderPageImageView.as_view(),
        name="reader-page-image",
    ),
    path(
        "reader/sessions/<uuid:session_key>/manifest",
        ReaderManifestView.as_view(),
        name="reader-manifest",
    ),
    path(
        "reader/sessions/<uuid:session_key>/pages/<int:page_number>/iiif/info.json",
        ReaderPageImageInfoView.as_view(),
        name="reader-page-image-info",
    ),
    path(
        "reader/sessions/<uuid:session_key>/pages/<int:page_number>/iiif/"
        "<str:region>/<str:size>/<str:rotation>/<str:quality>.<str:image_format>",
        ReaderPageTileView.as_view(),
        name="reader-page-tile",
    ),
    path(
        "reader/sessions/<uuid:session_key>/",
        ReaderSessionDeleteView.as_view(),
        name="reader-session-delete",
    ),
]
