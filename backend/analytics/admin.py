from django.contrib import admin

from analytics.models import AnalyticsRun, DailyUsageAggregate, InstitutionReport


class ReadOnlyAnalyticsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DailyUsageAggregate)
class DailyUsageAggregateAdmin(ReadOnlyAnalyticsAdmin):
    list_display = [
        "date",
        "organization",
        "document",
        "academic_domain",
        "access_model",
        "reader_session_count",
        "page_view_count",
        "distinct_document_count",
    ]
    list_filter = ["date", "access_model", "organization", "academic_domain"]
    search_fields = [
        "organization__name",
        "organization__slug",
        "document__title",
        "document__slug",
        "academic_domain__name",
        "academic_domain__slug",
    ]
    readonly_fields = [
        "date",
        "organization",
        "document",
        "academic_domain",
        "access_model",
        "reader_session_count",
        "page_view_count",
        "distinct_document_count",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["organization", "document", "academic_domain"]


@admin.register(InstitutionReport)
class InstitutionReportAdmin(ReadOnlyAnalyticsAdmin):
    list_display = ["organization", "period_start", "period_end", "status", "generated_at"]
    list_filter = ["status", "period_start", "period_end", "generated_at"]
    search_fields = ["organization__name", "organization__slug", "status"]
    readonly_fields = [
        "organization",
        "period_start",
        "period_end",
        "status",
        "metrics",
        "generated_at",
        "created_at",
        "updated_at",
    ]
    list_select_related = ["organization"]


@admin.register(AnalyticsRun)
class AnalyticsRunAdmin(ReadOnlyAnalyticsAdmin):
    list_display = [
        "run_type",
        "status",
        "organization",
        "period_start",
        "period_end",
        "started_at",
        "finished_at",
    ]
    list_filter = ["run_type", "status", "organization", "period_start", "period_end", "started_at"]
    search_fields = ["organization__name", "organization__slug", "run_type", "status"]
    readonly_fields = [
        "run_type",
        "status",
        "organization",
        "period_start",
        "period_end",
        "started_at",
        "finished_at",
        "error_message",
        "metadata",
    ]
    list_select_related = ["organization"]
