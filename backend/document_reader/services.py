from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import Entitlement
from accounts.services import user_has_entitlement
from catalog.models import Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage, ExtractedText
from document_reader.exceptions import ReaderAccessDenied, ReaderPageUnavailable, ReaderSessionInactive
from document_reader.models import PageAccessLog, ReaderSession


RESTRICTED_ACCESS_MODELS = {
    Document.AccessModel.SUBSCRIPTION,
    Document.AccessModel.INSTITUTION_ONLY,
    Document.AccessModel.SPONSORED,
    Document.AccessModel.RESTRICTED,
}


def document_requires_entitlement(document: Document) -> bool:
    return document.access_model in RESTRICTED_ACCESS_MODELS


def document_is_reader_accessible(document: Document) -> bool:
    return (
        document.publication_status == Document.PublicationStatus.PUBLISHED
        and document.access_model != Document.AccessModel.PRIVATE
    )


def _user_is_authenticated(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False))


def _user_has_document_read_entitlement(user, document: Document, at=None) -> bool:
    if user_has_entitlement(
        user=user,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=document.entitlement_scope_id,
        at=at,
    ):
        return True
    if document.academic_domain_id:
        return user_has_entitlement(
            user=user,
            access_right=Entitlement.AccessRight.READ,
            scope_type=Entitlement.ScopeType.DOMAIN,
            scope_id=str(document.academic_domain_id),
            at=at,
        )
    return False


def user_can_read_document(user, document: Document, at=None) -> bool:
    if not document_is_reader_accessible(document):
        return False
    if not document_requires_entitlement(document):
        return document.access_model == Document.AccessModel.FREE
    if not _user_is_authenticated(user):
        return False
    return _user_has_document_read_entitlement(user, document, at=at)


def get_current_processed_version(document: Document) -> DocumentVersion:
    versions = list(
        DocumentVersion.objects.filter(
            document=document,
            is_current=True,
            status=DocumentVersion.Status.PROCESSED,
            page_count__isnull=False,
            page_count__gt=0,
        ).order_by("-created_at")[:2]
    )
    if len(versions) != 1:
        raise ReaderAccessDenied("Document has no single readable current version")
    return versions[0]


def start_reader_session(
    *,
    user,
    document: Document,
    client_ip: str = "",
    user_agent: str = "",
    at=None,
) -> ReaderSession:
    at = at or timezone.now()
    if not user_can_read_document(user, document, at=at):
        raise ReaderAccessDenied("User cannot read this document")

    version = get_current_processed_version(document)
    ttl_minutes = int(getattr(settings, "READER_SESSION_TTL_MINUTES", 120))
    with transaction.atomic():
        return ReaderSession.objects.create(
            user=user,
            document=document,
            version=version,
            started_at=at,
            expires_at=at + timezone.timedelta(minutes=ttl_minutes),
            client_ip=client_ip,
            user_agent=user_agent,
            last_seen_at=at,
        )


def end_reader_session(*, session: ReaderSession, at=None) -> ReaderSession:
    return session.end(at=at)


def _ensure_reader_session_can_read(session: ReaderSession, at=None):
    if not session.is_active_at(at=at):
        raise ReaderSessionInactive("Reader session is not active")
    if not user_can_read_document(session.user, session.document, at=at):
        raise ReaderAccessDenied("User can no longer read this document")
    if (
        not session.version.is_current
        or session.version.status != DocumentVersion.Status.PROCESSED
        or not session.version.page_count
    ):
        raise ReaderAccessDenied("Reader session version is no longer readable")


def get_reader_page(*, session: ReaderSession, page_number: int, at=None) -> dict:
    at = at or timezone.now()
    if page_number < 1:
        raise ReaderPageUnavailable("page_number must be positive")

    session.refresh_from_db()
    _ensure_reader_session_can_read(session, at=at)

    if page_number > session.version.page_count:
        raise ReaderPageUnavailable("Page is outside the readable document range")

    try:
        page = DocumentPage.objects.get(
            version=session.version,
            page_number=page_number,
            status=DocumentPage.Status.PROCESSED,
        )
    except DocumentPage.DoesNotExist as exc:
        raise ReaderPageUnavailable("Page is not available for reading") from exc

    try:
        extracted_text = ExtractedText.objects.get(page=page)
    except ExtractedText.DoesNotExist as exc:
        raise ReaderPageUnavailable("Page has no extracted text") from exc

    with transaction.atomic():
        PageAccessLog.objects.create(
            session=session,
            page=page,
            user=session.user,
            document=session.document,
            page_number=page.page_number,
            client_ip=session.client_ip,
            user_agent=session.user_agent,
        )
        session.last_seen_at = at
        session.save(update_fields=["last_seen_at", "updated_at"])

    return {
        "session_key": str(session.session_key),
        "document_id": session.document_id,
        "version_id": session.version_id,
        "page_number": page.page_number,
        "page_count": session.version.page_count,
        "language_code": extracted_text.language_code,
        "text": extracted_text.text,
    }
