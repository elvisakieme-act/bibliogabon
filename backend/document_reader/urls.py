from django.urls import path

from document_reader import views


urlpatterns = [
    path(
        "documents/<int:document_id>/sessions/",
        views.create_reader_session,
        name="reader-session-create",
    ),
    path(
        "sessions/<uuid:session_key>/pages/<int:page_number>/",
        views.reader_page,
        name="reader-page",
    ),
    path(
        "sessions/<uuid:session_key>/end/",
        views.end_reader_session_view,
        name="reader-session-end",
    ),
]
