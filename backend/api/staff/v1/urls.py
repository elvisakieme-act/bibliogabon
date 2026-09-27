from django.urls import path

from api.staff.v1.contributors import (
    DocumentAuthorDetailView,
    DocumentAuthorListView,
    DocumentRightsDecisionView,
    DocumentRightsView,
)
from api.staff.v1.deposit import DocumentSourceView
from api.staff.v1.documents import (
    StaffDocumentDetailView,
    StaffDocumentListView,
    StaffDocumentSubmitView,
)
from api.staff.v1.views import StaffIndexView


app_name = "api-staff-v1"

urlpatterns = [
    path("", StaffIndexView.as_view(), name="index"),
    path("documents/", StaffDocumentListView.as_view(), name="document-list"),
    path("documents/<int:document_id>/", StaffDocumentDetailView.as_view(), name="document-detail"),
    path("documents/<int:document_id>/submit/", StaffDocumentSubmitView.as_view(), name="document-submit"),
    path("documents/<int:document_id>/authors/", DocumentAuthorListView.as_view(), name="document-authors"),
    path(
        "documents/<int:document_id>/authors/<int:author_id>/",
        DocumentAuthorDetailView.as_view(),
        name="document-author-detail",
    ),
    path("documents/<int:document_id>/source/", DocumentSourceView.as_view(), name="document-source"),
    path("documents/<int:document_id>/rights/", DocumentRightsView.as_view(), name="document-rights"),
    path(
        "documents/<int:document_id>/rights/decision/",
        DocumentRightsDecisionView.as_view(),
        name="document-rights-decision",
    ),
]
