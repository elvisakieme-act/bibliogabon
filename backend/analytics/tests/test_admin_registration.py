import pytest
from django.contrib import admin
from django.test import RequestFactory

from analytics.admin import AnalyticsRunAdmin, DailyUsageAggregateAdmin, InstitutionReportAdmin
from analytics.models import AnalyticsRun, DailyUsageAggregate, InstitutionReport
from analytics.tests.factories import create_organization


def test_analytics_models_are_registered_in_admin():
    assert isinstance(admin.site._registry[DailyUsageAggregate], DailyUsageAggregateAdmin)
    assert isinstance(admin.site._registry[InstitutionReport], InstitutionReportAdmin)
    assert isinstance(admin.site._registry[AnalyticsRun], AnalyticsRunAdmin)


@pytest.mark.django_db
def test_analytics_admins_are_read_only():
    request = RequestFactory().get("/admin/analytics/")
    request.user = type(
        "StaffUser",
        (),
        {"is_active": True, "is_staff": True, "has_perm": lambda self, perm: True},
    )()
    organization = create_organization(slug="admin-report-org")
    report = InstitutionReport.objects.create(
        organization=organization,
        period_start="2026-01-01",
        period_end="2026-01-31",
        metrics={},
    )

    report_admin = admin.site._registry[InstitutionReport]

    assert report_admin.has_add_permission(request) is False
    assert report_admin.has_change_permission(request, report) is False
    assert report_admin.has_delete_permission(request, report) is False
