from django.contrib import admin

from document_processing.models import DocumentPage, ExtractedText, SearchIndexRecord


@admin.register(DocumentPage)
class DocumentPageAdmin(admin.ModelAdmin):
    list_display = ["version", "page_number", "status", "created_by_job", "created_at"]
    list_filter = ["status"]
    search_fields = ["version__document__title", "version__version_label"]
    autocomplete_fields = ["version", "created_by_job"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ExtractedText)
class ExtractedTextAdmin(admin.ModelAdmin):
    list_display = ["page", "language_code", "extraction_method", "confidence", "created_by_job"]
    list_filter = ["language_code", "extraction_method"]
    search_fields = ["page__version__document__title", "text"]
    autocomplete_fields = ["page", "created_by_job"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SearchIndexRecord)
class SearchIndexRecordAdmin(admin.ModelAdmin):
    list_display = ["page", "status", "language_code", "content_hash", "indexed_at"]
    list_filter = ["status", "language_code"]
    search_fields = ["page__version__document__title", "content_hash", "error_code"]
    autocomplete_fields = ["page"]
    readonly_fields = ["created_at", "updated_at", "indexed_at"]
