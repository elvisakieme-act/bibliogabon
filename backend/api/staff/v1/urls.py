from django.urls import path

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
]
