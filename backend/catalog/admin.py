from django.contrib import admin

from catalog.models import (
    AcademicDomain,
    Author,
    Collection,
    CollectionItem,
    Document,
    DocumentAuthor,
    DocumentType,
    RightsAgreement,
)


@admin.register(AcademicDomain)
class AcademicDomainAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "icon", "color", "display_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["display_name", "author_type", "affiliation", "linked_user"]
    list_filter = ["author_type"]
    search_fields = [
        "display_name",
        "normalized_name",
        "affiliation",
        "contact_email",
    ]
    autocomplete_fields = ["linked_user"]


class DocumentAuthorInline(admin.TabularInline):
    model = DocumentAuthor
    extra = 1
    autocomplete_fields = ["author"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "document_type",
        "publication_status",
        "category",
        "access_model",
        "academic_domain",
        "owner_organization",
    ]
    list_filter = [
        "document_type",
        "publication_status",
        "category",
        "access_model",
        "academic_domain",
    ]
    search_fields = ["title", "slug", "abstract"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["document_type", "academic_domain", "owner_organization"]
    inlines = [DocumentAuthorInline]
    readonly_fields = ["created_at", "updated_at", "published_at", "withdrawn_at"]


@admin.register(DocumentAuthor)
class DocumentAuthorAdmin(admin.ModelAdmin):
    list_display = ["document", "author", "role", "position"]
    list_filter = ["role"]
    search_fields = ["document__title", "author__display_name"]
    autocomplete_fields = ["document", "author"]


class CollectionItemInline(admin.TabularInline):
    model = CollectionItem
    extra = 1
    autocomplete_fields = ["document"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "status",
        "academic_domain",
        "owner_organization",
        "is_active",
    ]
    list_filter = ["status", "is_active", "academic_domain"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["academic_domain", "owner_organization"]
    inlines = [CollectionItemInline]


@admin.register(CollectionItem)
class CollectionItemAdmin(admin.ModelAdmin):
    list_display = ["collection", "document", "position"]
    search_fields = ["collection__name", "document__title"]
    autocomplete_fields = ["collection", "document"]


@admin.register(RightsAgreement)
class RightsAgreementAdmin(admin.ModelAdmin):
    list_display = [
        "document",
        "rights_holder_name",
        "agreement_type",
        "authorization_status",
        "authorization_date",
    ]
    list_filter = ["agreement_type", "authorization_status", "withdrawal_rule"]
    search_fields = [
        "document__title",
        "rights_holder_name",
        "consent_reference",
        "audit_reference",
    ]
    autocomplete_fields = ["document"]
