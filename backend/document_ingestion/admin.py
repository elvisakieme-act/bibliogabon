from django.contrib import admin

from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = [
        "document",
        "version_label",
        "status",
        "is_current",
        "uploaded_by",
        "created_at",
    ]
    list_filter = ["status", "is_current", "source_retention_policy"]
    search_fields = ["document__title", "version_label", "processing_summary"]
    autocomplete_fields = ["document", "uploaded_by"]
    readonly_fields = ["created_at", "updated_at", "processed_at"]


@admin.register(DocumentAsset)
class DocumentAssetAdmin(admin.ModelAdmin):
    list_display = [
        "version",
        "asset_type",
        "storage_bucket",
        "storage_key",
        "mime_type",
        "byte_size",
        "visibility",
    ]
    list_filter = ["asset_type", "visibility", "mime_type"]
    search_fields = ["version__document__title", "storage_key", "checksum_sha256"]
    autocomplete_fields = ["version", "created_by_job"]
    readonly_fields = ["created_at"]


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = [
        "job_type",
        "version",
        "status",
        "retry_count",
        "idempotency_key",
        "created_at",
    ]
    list_filter = ["job_type", "status"]
    search_fields = ["version__document__title", "idempotency_key", "celery_task_id", "error_code"]
    autocomplete_fields = ["version", "source_asset"]
    readonly_fields = ["created_at", "updated_at", "started_at", "completed_at", "failed_at"]
