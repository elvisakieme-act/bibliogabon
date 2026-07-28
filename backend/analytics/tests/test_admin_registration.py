import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.utils import timezone

from analytics.admin import AnalyticsRunAdmin, DailyUsageAggregateAdmin, InstitutionReportAdmin
from analytics.models import AnalyticsRun, DailyUsageAggregate, InstitutionReport
from analytics.tests.factories import create_document, create_organization


def _staff_request():
    request = RequestFactory().get("/admin/analytics/")
    request.user = type(
        "StaffUser",
        (),
        {"is_active": True, "is_staff": True, "has_perm": lambda self, perm: True},
    )()
    return request


def _create_admin_object(model):
    organization = create_organization(slug=f"admin-{model._meta.model_name}")
    if model is DailyUsageAggregate:
        document = create_document(slug="admin-aggregate-document")
        return DailyUsageAggregate.objects.create(
            date=timezone.datetime(2026, 1, 1).date(),
            organization=organization,
            document=document,
            academic_domain=document.academic_domain,
            access_model=document.access_model,
        )
    if model is InstitutionReport:
        return InstitutionReport.objects.create(
            organization=organization,
            period_start="2026-01-01",
            period_end="2026-01-31",
            metrics={},
        )
    return AnalyticsRun.objects.create(
        run_type=AnalyticsRun.RunType.INSTITUTION_REPORT,
        organization=organization,
        period_start="2026-01-01",
        period_end="2026-01-31",
    )


def _admin_surface_fields(model_admin):
    exposed = set()
    for attribute in ["list_display", "list_filter", "search_fields", "readonly_fields"]:
        exposed.update(getattr(model_admin, attribute, []))
    return exposed


def test_analytics_models_are_registered_in_admin():
    assert isinstance(admin.site._registry[DailyUsageAggregate], DailyUsageAggregateAdmin)
    assert isinstance(admin.site._registry[InstitutionReport], InstitutionReportAdmin)
    assert isinstance(admin.site._registry[AnalyticsRun], AnalyticsRunAdmin)


@pytest.mark.django_db
@pytest.mark.parametrize("model", [DailyUsageAggregate, InstitutionReport, AnalyticsRun])
def test_analytics_admins_are_read_only(model):
    request = _staff_request()
    obj = _create_admin_object(model)
    model_admin = admin.site._registry[model]

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request, obj) is False
    assert model_admin.has_delete_permission(request, obj) is False


@pytest.mark.parametrize("model", [DailyUsageAggregate, InstitutionReport, AnalyticsRun])
def test_analytics_admin_surfaces_do_not_expose_personal_fields(model):
    model_admin = admin.site._registry[model]

    assert _admin_surface_fields(model_admin).isdisjoint(
        {
            "email",
            "generated_by",
            "generated_by__email",
            "generated_by__display_name",
            "user",
            "user__email",
            "user__display_name",
        }
    )
