import pytest
from django.utils import timezone

from analytics.models import DailyUsageAggregate
from analytics.services import build_daily_usage_aggregate
from analytics.tests.factories import (
    create_active_membership,
    create_document,
    create_organization,
    create_reader_activity,
    create_user,
)


@pytest.mark.django_db
def test_daily_usage_aggregate_counts_single_organization_activity():
    at = timezone.make_aware(timezone.datetime(2026, 1, 15, 10, 0, 0))
    user = create_user()
    organization = create_organization(slug="uob")
    create_active_membership(user, organization, starts_at=at - timezone.timedelta(days=1))
    document = create_document(slug="macro", access_model="subscription")
    create_reader_activity(user=user, document=document, started_at=at, page_views=2)

    aggregates = build_daily_usage_aggregate(at.date())

    assert len(aggregates) == 1
    aggregate = DailyUsageAggregate.objects.get()
    assert aggregate.organization == organization
    assert aggregate.document == document
    assert aggregate.academic_domain == document.academic_domain
    assert aggregate.access_model == document.access_model
    assert aggregate.reader_session_count == 1
    assert aggregate.page_view_count == 2
    assert aggregate.distinct_document_count == 1


@pytest.mark.django_db
def test_daily_usage_aggregate_rebuild_updates_existing_row():
    at = timezone.make_aware(timezone.datetime(2026, 1, 15, 10, 0, 0))
    user = create_user(email="repeat@example.ga")
    organization = create_organization(slug="ustm")
    create_active_membership(user, organization, starts_at=at - timezone.timedelta(days=1))
    document = create_document(slug="math")
    create_reader_activity(user=user, document=document, started_at=at, page_views=1)

    first = build_daily_usage_aggregate(at.date())[0]
    create_reader_activity(user=user, document=document, started_at=at + timezone.timedelta(hours=1), page_views=2)
    second = build_daily_usage_aggregate(at.date())[0]

    assert first.pk == second.pk
    assert DailyUsageAggregate.objects.count() == 1
    assert second.reader_session_count == 2
    assert second.page_view_count == 3


@pytest.mark.django_db
def test_daily_usage_aggregate_rebuild_removes_stale_rows_when_activity_becomes_ambiguous():
    at = timezone.make_aware(timezone.datetime(2026, 1, 15, 10, 0, 0))
    day = at.date()
    user = create_user(email="ambiguous-rebuild@example.ga")
    first_org = create_organization(slug="rebuild-org-a")
    second_org = create_organization(slug="rebuild-org-b")
    create_active_membership(user, first_org, starts_at=at - timezone.timedelta(days=1))
    document = create_document(slug="stale-attribution")
    create_reader_activity(user=user, document=document, started_at=at, page_views=1)

    first = build_daily_usage_aggregate(day)
    create_active_membership(user, second_org, starts_at=at - timezone.timedelta(days=1))
    second = build_daily_usage_aggregate(day)

    assert len(first) == 1
    assert second == []
    assert DailyUsageAggregate.objects.filter(date=day).count() == 0


@pytest.mark.django_db
def test_daily_usage_aggregate_excludes_ambiguous_multi_organization_activity():
    at = timezone.make_aware(timezone.datetime(2026, 1, 15, 10, 0, 0))
    user = create_user(email="multi@example.ga")
    first_org = create_organization(slug="org-a")
    second_org = create_organization(slug="org-b")
    create_active_membership(user, first_org, starts_at=at - timezone.timedelta(days=1))
    create_active_membership(user, second_org, starts_at=at - timezone.timedelta(days=1))
    document = create_document(slug="ambiguous")
    create_reader_activity(user=user, document=document, started_at=at, page_views=1)

    aggregates = build_daily_usage_aggregate(at.date())

    assert aggregates == []
    assert DailyUsageAggregate.objects.count() == 0
