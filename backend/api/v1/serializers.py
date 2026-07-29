from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from rest_framework import serializers

from catalog.models import DocumentAuthor
from document_ingestion.models import DocumentVersion
from document_reader.services import document_requires_entitlement, user_can_read_document


def serialize_user(user) -> dict:
    return {
        "id": user.pk,
        "email": user.email,
        "display_name": user.display_name,
        "account_type": user.account_type,
    }


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=160)

    def validate_email(self, value):
        email = get_user_model().objects.normalize_email(value)
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "A user with this email already exists.",
                code="email_exists",
            )
        return email


class CurrentUserUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=32)


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    account_type = serializers.CharField(read_only=True)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class TokenRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class RegisterResponseSerializer(serializers.Serializer):
    user = UserSerializer(read_only=True)
    tokens = TokenPairSerializer(read_only=True)


class ErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    field_errors = serializers.DictField(read_only=True)


class ErrorResponseSerializer(serializers.Serializer):
    error = ErrorDetailSerializer(read_only=True)


class ReaderSessionCreateSerializer(serializers.Serializer):
    document_id = serializers.IntegerField(min_value=1)


class ReaderSessionSerializer(serializers.Serializer):
    session_key = serializers.UUIDField(read_only=True)
    document_id = serializers.IntegerField(read_only=True)
    version_id = serializers.IntegerField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)


class ReaderPageSerializer(serializers.Serializer):
    session_key = serializers.UUIDField(read_only=True)
    document_id = serializers.IntegerField(read_only=True)
    version_id = serializers.IntegerField(read_only=True)
    page_number = serializers.IntegerField(read_only=True)
    page_count = serializers.IntegerField(read_only=True)
    language_code = serializers.CharField(read_only=True)
    text = serializers.CharField(read_only=True)


def document_metadata_prefetches(prefix: str = "") -> list[Prefetch]:
    return [
        Prefetch(
            f"{prefix}document_authors",
            queryset=DocumentAuthor.objects.select_related("author").order_by("position"),
            to_attr="_api_document_authors",
        ),
        Prefetch(
            f"{prefix}versions",
            queryset=DocumentVersion.objects.filter(is_current=True).order_by("-created_at"),
            to_attr="_api_current_versions",
        ),
    ]


def _ordered_authors(document) -> list[dict]:
    authorships = getattr(document, "_api_document_authors", None)
    if authorships is None:
        authorships = document.document_authors.select_related("author").order_by("position")
    return [
        {
            "id": authorship.author_id,
            "display_name": authorship.author.display_name,
            "role": authorship.role,
        }
        for authorship in authorships
    ]


def _page_count(document) -> int | None:
    current_versions = getattr(document, "_api_current_versions", None)
    if current_versions is not None:
        return current_versions[0].page_count if current_versions else None
    version = (
        DocumentVersion.objects.filter(document=document, is_current=True)
        .order_by("-created_at")
        .first()
    )
    return version.page_count if version else None


def _access_block(document, user=None, readable_document_ids: set[int] | None = None) -> dict:
    access_model = document.access_model
    can_read = (
        document.pk in readable_document_ids
        if readable_document_ids is not None
        else user_can_read_document(user, document)
    )
    if can_read:
        reason = "free" if not document_requires_entitlement(document) else "active_entitlement"
        return {"can_read": True, "access_model": access_model, "reason": reason}
    if document_requires_entitlement(document) and not getattr(user, "is_authenticated", False):
        return {"can_read": False, "access_model": access_model, "reason": "authentication_required"}
    if document_requires_entitlement(document):
        return {"can_read": False, "access_model": access_model, "reason": "entitlement_required"}
    return {"can_read": False, "access_model": access_model, "reason": "unavailable"}


def serialize_document_metadata(
    document,
    user=None,
    readable_document_ids: set[int] | None = None,
) -> dict:
    domain = None
    if document.academic_domain_id:
        domain = {
            "id": document.academic_domain_id,
            "name": document.academic_domain.name,
            "slug": document.academic_domain.slug,
        }
    owner = document.owner_organization.name if document.owner_organization_id else None
    return {
        "id": document.pk,
        "slug": document.slug,
        "title": document.title,
        "abstract": document.abstract,
        "language_code": document.language_code,
        "publication_year": document.publication_year,
        "document_type": document.category,
        "access_model": document.access_model,
        "domain": domain,
        "authors": _ordered_authors(document),
        "owner": owner,
        "page_count": _page_count(document),
        "cover": None,
        "access": _access_block(
            document,
            user=user,
            readable_document_ids=readable_document_ids,
        ),
    }


class DocumentMetadataSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    slug = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    abstract = serializers.CharField(read_only=True)
    language_code = serializers.CharField(read_only=True)
    publication_year = serializers.IntegerField(read_only=True, allow_null=True)
    document_type = serializers.CharField(read_only=True)
    access_model = serializers.CharField(read_only=True)
    domain = serializers.DictField(read_only=True, allow_null=True)
    authors = serializers.ListField(child=serializers.DictField(), read_only=True)
    owner = serializers.CharField(read_only=True, allow_null=True)
    page_count = serializers.IntegerField(read_only=True, allow_null=True)
    cover = serializers.URLField(read_only=True, allow_null=True)
    access = serializers.DictField(read_only=True)


class DomainSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)


class AuthorMetadataSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    author_type = serializers.CharField(read_only=True)


class SearchResultSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    abstract = serializers.CharField(read_only=True)
    language_code = serializers.CharField(read_only=True)
    publication_year = serializers.IntegerField(read_only=True, allow_null=True)
    domain = serializers.DictField(read_only=True, allow_null=True)
    authors = serializers.ListField(child=serializers.CharField(), read_only=True)
    access_model = serializers.CharField(read_only=True)
    indexed_page_count = serializers.IntegerField(read_only=True)
    score = serializers.IntegerField(read_only=True)
    text_match = serializers.BooleanField(read_only=True)


class DocumentMetadataPageSerializer(serializers.Serializer):
    count = serializers.IntegerField(read_only=True)
    next = serializers.URLField(read_only=True, allow_null=True)
    previous = serializers.URLField(read_only=True, allow_null=True)
    results = DocumentMetadataSerializer(many=True, read_only=True)


class DomainPageSerializer(serializers.Serializer):
    count = serializers.IntegerField(read_only=True)
    next = serializers.URLField(read_only=True, allow_null=True)
    previous = serializers.URLField(read_only=True, allow_null=True)
    results = DomainSerializer(many=True, read_only=True)


class AuthorMetadataPageSerializer(serializers.Serializer):
    count = serializers.IntegerField(read_only=True)
    next = serializers.URLField(read_only=True, allow_null=True)
    previous = serializers.URLField(read_only=True, allow_null=True)
    results = AuthorMetadataSerializer(many=True, read_only=True)


class SearchResultPageSerializer(serializers.Serializer):
    count = serializers.IntegerField(read_only=True)
    next = serializers.URLField(read_only=True, allow_null=True)
    previous = serializers.URLField(read_only=True, allow_null=True)
    results = SearchResultSerializer(many=True, read_only=True)


class FavoriteCreateSerializer(serializers.Serializer):
    document_id = serializers.IntegerField(min_value=1)


class FavoriteSerializer(serializers.Serializer):
    document = DocumentMetadataSerializer(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class FavoritePageSerializer(serializers.Serializer):
    count = serializers.IntegerField(read_only=True)
    next = serializers.URLField(read_only=True, allow_null=True)
    previous = serializers.URLField(read_only=True, allow_null=True)
    results = FavoriteSerializer(many=True, read_only=True)


class ReadingProgressUpdateSerializer(serializers.Serializer):
    last_page_number = serializers.IntegerField(min_value=1)


class ReadingProgressSerializer(serializers.Serializer):
    document = DocumentMetadataSerializer(read_only=True)
    last_page_number = serializers.IntegerField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class ReadingProgressPageSerializer(serializers.Serializer):
    count = serializers.IntegerField(read_only=True)
    next = serializers.URLField(read_only=True, allow_null=True)
    previous = serializers.URLField(read_only=True, allow_null=True)
    results = ReadingProgressSerializer(many=True, read_only=True)
