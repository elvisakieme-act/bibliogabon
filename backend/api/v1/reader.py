from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.errors import error_response
from api.v1.serializers import (
    ErrorResponseSerializer,
    ReaderPageSerializer,
    ReaderSessionCreateSerializer,
    ReaderSessionSerializer,
)
from catalog.models import Document
from document_reader.exceptions import ReaderAccessDenied, ReaderPageUnavailable, ReaderSessionInactive
from document_reader.models import ReaderSession
from document_reader.services import (
    document_requires_entitlement,
    end_reader_session,
    get_reader_page,
    start_reader_session,
)


def _client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:45]
    return request.META.get("REMOTE_ADDR", "")[:45]


def _user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:300]


class ReaderSessionCreateView(APIView):
    @extend_schema(
        tags=["Reader"],
        summary="Start a controlled reader session",
        description="Free documents allow anonymous controlled reader sessions. Restricted documents require JWT authentication and active read entitlement.",
        request=ReaderSessionCreateSerializer,
        responses={
            201: ReaderSessionSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def post(self, request):
        document_id = request.data.get("document_id")
        if not document_id:
            return error_response(
                code="document_required",
                message="document_id is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors={"document_id": ["This field is required."]},
            )
        try:
            document = Document.objects.get(pk=document_id)
        except (TypeError, ValueError, Document.DoesNotExist):
            return error_response(
                code="not_found",
                message="Document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        user = request.user if request.user.is_authenticated else None
        if document_requires_entitlement(document) and user is None:
            return error_response(
                code="authentication_required",
                message="Authentication is required for this document.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            session = start_reader_session(
                user=user,
                document=document,
                client_ip=_client_ip(request),
                user_agent=_user_agent(request),
            )
        except ReaderAccessDenied:
            return error_response(
                code="entitlement_required",
                message="An active read entitlement is required.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {
                "session_key": str(session.session_key),
                "document_id": session.document_id,
                "version_id": session.version_id,
                "expires_at": session.expires_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class ReaderPageView(APIView):
    @extend_schema(
        tags=["Reader"],
        summary="Retrieve a controlled reader page",
        description="Free documents allow anonymous controlled reader sessions. Restricted documents require JWT authentication and active read entitlement.",
        responses={
            200: ReaderPageSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, session_key, page_number: int):
        try:
            session = ReaderSession.objects.select_related("user", "document", "version").get(
                session_key=session_key
            )
        except ReaderSession.DoesNotExist:
            return error_response("not_found", "Reader session not found.", status.HTTP_404_NOT_FOUND)
        if session.user_id and session.user_id != getattr(request.user, "pk", None):
            return error_response("access_denied", "This session belongs to another user.", status.HTTP_403_FORBIDDEN)
        try:
            return Response(get_reader_page(session=session, page_number=page_number), status=status.HTTP_200_OK)
        except ReaderSessionInactive:
            return error_response("session_inactive", "Reader session is inactive.", status.HTTP_403_FORBIDDEN)
        except ReaderAccessDenied:
            return error_response("entitlement_required", "An active read entitlement is required.", status.HTTP_403_FORBIDDEN)
        except ReaderPageUnavailable:
            return error_response("not_found", "Page not found.", status.HTTP_404_NOT_FOUND)


class ReaderSessionDeleteView(APIView):
    @extend_schema(
        tags=["Reader"],
        summary="End a controlled reader session",
        description="Free documents allow anonymous controlled reader sessions. Restricted documents require JWT authentication and active read entitlement.",
        responses={204: None, 403: ErrorResponseSerializer},
    )
    def delete(self, request, session_key):
        try:
            session = ReaderSession.objects.get(session_key=session_key)
        except ReaderSession.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if session.user_id and session.user_id != getattr(request.user, "pk", None):
            return error_response("access_denied", "This session belongs to another user.", status.HTTP_403_FORBIDDEN)
        end_reader_session(session=session)
        return Response(status=status.HTTP_204_NO_CONTENT)
