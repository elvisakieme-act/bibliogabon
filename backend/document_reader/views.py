from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from catalog.models import Document
from document_reader.exceptions import ReaderAccessDenied, ReaderPageUnavailable, ReaderSessionInactive
from document_reader.models import ReaderSession
from document_reader.services import end_reader_session, get_reader_page, start_reader_session


def _error(code: str, status: int) -> JsonResponse:
    return JsonResponse({"error": code}, status=status)


def _client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:45]
    return request.META.get("REMOTE_ADDR", "")[:45]


def _user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:300]


def _require_authenticated(request):
    if not request.user.is_authenticated:
        return _error("authentication_required", 401)
    return None


@require_POST
def create_reader_session(request, document_id: int) -> JsonResponse:
    auth_error = _require_authenticated(request)
    if auth_error:
        return auth_error

    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return _error("not_found", 404)

    try:
        session = start_reader_session(
            user=request.user,
            document=document,
            client_ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except ReaderAccessDenied:
        return _error("access_denied", 403)

    return JsonResponse(
        {
            "session_key": str(session.session_key),
            "document_id": session.document_id,
            "version_id": session.version_id,
            "expires_at": session.expires_at.isoformat(),
        },
        status=201,
    )


@require_GET
def reader_page(request, session_key, page_number: int) -> JsonResponse:
    auth_error = _require_authenticated(request)
    if auth_error:
        return auth_error

    try:
        session = ReaderSession.objects.select_related("user", "document", "version").get(
            session_key=session_key
        )
    except ReaderSession.DoesNotExist:
        return _error("not_found", 404)

    if session.user_id != request.user.pk:
        return _error("access_denied", 403)

    try:
        return JsonResponse(get_reader_page(session=session, page_number=page_number), status=200)
    except ReaderSessionInactive:
        return _error("session_inactive", 403)
    except ReaderAccessDenied:
        return _error("access_denied", 403)
    except ReaderPageUnavailable:
        return _error("not_found", 404)


@require_POST
def end_reader_session_view(request, session_key) -> JsonResponse:
    auth_error = _require_authenticated(request)
    if auth_error:
        return auth_error

    try:
        session = ReaderSession.objects.get(session_key=session_key)
    except ReaderSession.DoesNotExist:
        return _error("not_found", 404)

    if session.user_id != request.user.pk:
        return _error("access_denied", 403)

    session = end_reader_session(session=session)
    return JsonResponse({"session_key": str(session.session_key), "status": session.status}, status=200)
