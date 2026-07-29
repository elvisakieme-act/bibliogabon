from django.contrib import admin

from document_reader.models import FavoriteDocument, PageAccessLog, ReaderSession, ReadingProgress


@admin.register(ReaderSession)
class ReaderSessionAdmin(admin.ModelAdmin):
    list_display = ["session_key", "user", "document", "version", "status", "expires_at"]
    list_filter = ["status", "document__access_model", "document__publication_status"]
    search_fields = ["session_key", "user__email", "document__title", "version__version_label"]
    autocomplete_fields = ["user", "document", "version"]
    readonly_fields = ["session_key", "created_at", "updated_at", "started_at", "ended_at", "last_seen_at"]


@admin.register(PageAccessLog)
class PageAccessLogAdmin(admin.ModelAdmin):
    list_display = ["user", "document", "page_number", "session", "accessed_at"]
    list_filter = ["document__access_model", "accessed_at"]
    search_fields = ["user__email", "document__title", "session__session_key"]
    autocomplete_fields = ["session", "page", "user", "document"]
    readonly_fields = ["accessed_at"]


@admin.register(FavoriteDocument)
class FavoriteDocumentAdmin(admin.ModelAdmin):
    list_display = ["user", "document", "created_at"]
    search_fields = ["user__email", "document__title"]
    list_filter = ["created_at"]


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "document", "last_page_number", "updated_at"]
    search_fields = ["user__email", "document__title"]
    list_filter = ["updated_at"]
