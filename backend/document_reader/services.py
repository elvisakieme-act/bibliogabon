from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import Entitlement
from accounts.services import user_has_entitlement
from catalog.models import Document
from document_ingestion.models import DocumentVersion
from document_reader.exceptions import ReaderAccessDenied
from document_reader.models import ReaderSession


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
    if not _user_is_authenticated(user):
        return False
    if not document_is_reader_accessible(document):
        return False
    if not document_requires_entitlement(document):
        return document.access_model == Document.AccessModel.FREE
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
