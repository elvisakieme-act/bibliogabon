from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Entitlement
from accounts.services import active_organization_ids_for_user, user_has_entitlement
from catalog.models import Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage, ExtractedText
from document_reader.exceptions import ReaderAccessDenied, ReaderPageUnavailable, ReaderSessionInactive
from document_reader.models import FavoriteDocument, PageAccessLog, ReaderSession, ReadingProgress


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


def readable_document_ids_for_user(user, documents, at=None) -> set[int]:
    documents = list(documents)
    readable_ids = {
        document.pk
        for document in documents
        if document_is_reader_accessible(document)
        and not document_requires_entitlement(document)
        and document.access_model == Document.AccessModel.FREE
    }
    restricted_documents = [
        document
        for document in documents
        if document_is_reader_accessible(document) and document_requires_entitlement(document)
    ]
    if not restricted_documents or not _user_is_authenticated(user):
        return readable_ids

    at = at or timezone.now()
    organization_ids = active_organization_ids_for_user(user, at=at)
    entitlements = Entitlement.objects.filter(
        Q(user=user) | Q(user__isnull=True, organization_id__in=organization_ids),
        access_right=Entitlement.AccessRight.READ,
        scope_type__in=[
            Entitlement.ScopeType.GLOBAL,
            Entitlement.ScopeType.DOMAIN,
            Entitlement.ScopeType.DOCUMENT,
        ],
        starts_at__lte=at,
        revoked_at__isnull=True,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))

    has_global_access = False
    domain_scope_ids = set()
    document_scope_ids = set()
    for entitlement in entitlements:
        if entitlement.scope_type == Entitlement.ScopeType.GLOBAL:
            has_global_access = True
        elif entitlement.scope_type == Entitlement.ScopeType.DOMAIN:
            domain_scope_ids.add(entitlement.scope_id)
        elif entitlement.scope_type == Entitlement.ScopeType.DOCUMENT:
            document_scope_ids.add(entitlement.scope_id)

    for document in restricted_documents:
        if (
            has_global_access
            or document.entitlement_scope_id in document_scope_ids
            or (
                document.academic_domain_id
                and str(document.academic_domain_id) in domain_scope_ids
            )
        ):
            readable_ids.add(document.pk)
    return readable_ids


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


def favorite_document(user, document: Document) -> tuple[FavoriteDocument, bool]:
    if not document_is_reader_accessible(document):
        raise ReaderAccessDenied("Document is not discoverable")
    return FavoriteDocument.objects.get_or_create(user=user, document=document)


def remove_favorite(user, document: Document) -> bool:
    deleted_count, _ = FavoriteDocument.objects.filter(user=user, document=document).delete()
    return deleted_count > 0


def record_reading_progress(user, document: Document, last_page_number: int) -> ReadingProgress:
    if last_page_number < 1:
        raise ReaderPageUnavailable("last_page_number must be positive")
    if not user_can_read_document(user, document):
        raise ReaderAccessDenied("User cannot record progress for this document")
    version = get_current_processed_version(document)
    if last_page_number > version.page_count:
        raise ReaderPageUnavailable("last_page_number is outside the readable document range")
    progress, _ = ReadingProgress.objects.update_or_create(
        user=user,
        document=document,
        defaults={"last_page_number": last_page_number},
    )
    return progress


def start_reader_session(
    *,
    user,
    document: Document,
    client_ip: str = "",
    user_agent: str = "",
    at=None,
) -> ReaderSession:
    at = at or timezone.now()
    if user is not None and not _user_is_authenticated(user):
        raise ReaderAccessDenied("Anonymous users must be represented as None")
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
