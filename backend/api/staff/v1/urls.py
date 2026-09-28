from django.urls import path

from api.staff.v1.authors import StaffAuthorListView
from api.staff.v1.contributors import (
    DocumentAuthorDetailView,
    DocumentAuthorListView,
    DocumentRightsDecisionView,
    DocumentRightsView,
)
from api.staff.v1.deposit import DocumentIngestionView, DocumentSourceView
from api.staff.v1.documents import (
    StaffDocumentDetailView,
    StaffDocumentListView,
    StaffDocumentSubmitView,
)
from api.staff.v1.lifecycle import (
    DocumentArchiveView,
    DocumentAuditView,
    DocumentWithdrawView,
)
from api.staff.v1.reviews import (
    ReviewAssignView,
    ReviewDecisionView,
    ReviewDetailView,
    ReviewListView,
)
from api.staff.v1.tickets import (
    TicketAssignView,
    TicketDetailView,
    TicketListView,
    TicketResolveView,
)
from api.staff.v1.views import StaffIndexView

app_name = "api-staff-v1"

urlpatterns = [
    path("", StaffIndexView.as_view(), name="index"),
    path("authors/", StaffAuthorListView.as_view(), name="author-list"),
    path("tickets/", TicketListView.as_view(), name="ticket-list"),
    path("tickets/<int:ticket_id>/", TicketDetailView.as_view(), name="ticket-detail"),
    path(
        "tickets/<int:ticket_id>/assign/",
        TicketAssignView.as_view(),
        name="ticket-assign",
    ),
    path(
        "tickets/<int:ticket_id>/resolve/",
        TicketResolveView.as_view(),
        name="ticket-resolve",
    ),
    path("reviews/", ReviewListView.as_view(), name="review-list"),
    path("reviews/<int:review_id>/", ReviewDetailView.as_view(), name="review-detail"),
    path(
        "reviews/<int:review_id>/assign/",
        ReviewAssignView.as_view(),
        name="review-assign",
    ),
    path(
        "reviews/<int:review_id>/decision/",
        ReviewDecisionView.as_view(),
        name="review-decision",
    ),
    path("documents/", StaffDocumentListView.as_view(), name="document-list"),
    path(
        "documents/<int:document_id>/",
        StaffDocumentDetailView.as_view(),
        name="document-detail",
    ),
    path(
        "documents/<int:document_id>/submit/",
        StaffDocumentSubmitView.as_view(),
        name="document-submit",
    ),
    path(
        "documents/<int:document_id>/authors/",
        DocumentAuthorListView.as_view(),
        name="document-authors",
    ),
    path(
        "documents/<int:document_id>/authors/<int:author_id>/",
        DocumentAuthorDetailView.as_view(),
        name="document-author-detail",
    ),
    path(
        "documents/<int:document_id>/source/",
        DocumentSourceView.as_view(),
        name="document-source",
    ),
    path(
        "documents/<int:document_id>/ingestion/",
        DocumentIngestionView.as_view(),
        name="document-ingestion",
    ),
    path(
        "documents/<int:document_id>/withdraw/",
        DocumentWithdrawView.as_view(),
        name="document-withdraw",
    ),
    path(
        "documents/<int:document_id>/archive/",
        DocumentArchiveView.as_view(),
        name="document-archive",
    ),
    path(
        "documents/<int:document_id>/audit/",
        DocumentAuditView.as_view(),
        name="document-audit",
    ),
    path(
        "documents/<int:document_id>/rights/",
        DocumentRightsView.as_view(),
        name="document-rights",
    ),
    path(
        "documents/<int:document_id>/rights/decision/",
        DocumentRightsDecisionView.as_view(),
        name="document-rights-decision",
    ),
]
