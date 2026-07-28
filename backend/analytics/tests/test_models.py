import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Organization
from analytics.models import AnalyticsRun, DailyUsageAggregate, InstitutionReport
from catalog.models import AcademicDomain, Document


@pytest.mark.django_db
def test_daily_usage_aggregate_stores_aggregate_dimensions():
    organization = Organization.objects.create(name="UOB", slug="uob")
    domain = AcademicDomain.objects.create(name="Droit", slug="droit")
    document = Document.objects.create(
        title="Droit administratif",
        slug="droit-administratif",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )

    aggregate = DailyUsageAggregate.objects.create(
        date=timezone.datetime(2026, 1, 15).date(),
        organization=organization,
        document=document,
        academic_domain=domain,
        access_model=document.access_model,
        reader_session_count=2,
        page_view_count=9,
        distinct_document_count=1,
    )

    assert aggregate.organization == organization
    assert aggregate.document == document
    assert aggregate.academic_domain == domain
    assert aggregate.reader_session_count == 2
    assert aggregate.page_view_count == 9
    assert aggregate.distinct_document_count == 1


@pytest.mark.django_db
def test_daily_usage_aggregate_requires_current_aggregate_dimensions():
    aggregate_date = timezone.datetime(2026, 1, 15).date()
    aggregate = DailyUsageAggregate(
        date=aggregate_date,
        access_model=Document.AccessModel.FREE,
        reader_session_count=2,
        page_view_count=9,
        distinct_document_count=1,
    )

    with pytest.raises(ValidationError):
        aggregate.save()

    assert DailyUsageAggregate.objects.count() == 0


@pytest.mark.django_db
def test_institution_report_rejects_inverted_period():
    organization = Organization.objects.create(name="USTM", slug="ustm")
    report = InstitutionReport(
        organization=organization,
        period_start=timezone.datetime(2026, 1, 31).date(),
        period_end=timezone.datetime(2026, 1, 1).date(),
        metrics={},
    )

    with pytest.raises(ValidationError):
        report.save()


@pytest.mark.django_db
def test_analytics_run_rejects_non_object_metadata():
    run = AnalyticsRun(
        run_type=AnalyticsRun.RunType.INSTITUTION_REPORT,
        period_start=timezone.datetime(2026, 1, 1).date(),
        period_end=timezone.datetime(2026, 1, 31).date(),
        metadata=[],
    )

    with pytest.raises(ValidationError):
        run.save()
