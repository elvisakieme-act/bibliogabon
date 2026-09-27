from django.contrib import admin

from search_discovery.models import DocumentSearchIndex


@admin.register(DocumentSearchIndex)
class DocumentSearchIndexAdmin(admin.ModelAdmin):
    list_display = [
        "document",
        "type_slug",
        "language_code",
        "access_model",
        "domain_slug",
        "indexed_page_count",
        "indexed_at",
    ]
    list_filter = [
        "type_slug",
        "language_code",
        "access_model",
        "domain_slug",
        "publication_year",
    ]
    search_fields = ["document__title", "title", "type_name", "author_names", "metadata_text"]
    autocomplete_fields = ["document"]
    readonly_fields = ["metadata_text", "page_text", "created_at", "updated_at", "indexed_at"]
