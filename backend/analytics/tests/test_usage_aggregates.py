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
    create_reader_activity(
        user=user, document=document, started_at=at + timezone.timedelta(hours=1), page_views=2
    )
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


@pytest.mark.django_db
def test_attribution_follows_the_instant_of_the_activity_not_the_day():
    """Une adhesion qui commence en cours de journee n'attribue que ce qui
    suit. Resoudre l'organisation une fois par utilisateur, plutot qu'une
    fois par activite, aurait attribue la journee entiere."""
    morning = timezone.make_aware(timezone.datetime(2026, 3, 10, 8, 0, 0))
    joined_at = timezone.make_aware(timezone.datetime(2026, 3, 10, 12, 0, 0))
    afternoon = timezone.make_aware(timezone.datetime(2026, 3, 10, 16, 0, 0))

    user = create_user(email="mi-journee@example.ga")
    organization = create_organization(slug="mi-journee")
    create_active_membership(user, organization, starts_at=joined_at)
    document = create_document(slug="mi-journee-doc")
    create_reader_activity(user=user, document=document, started_at=morning, page_views=3)
    create_reader_activity(user=user, document=document, started_at=afternoon, page_views=2)

    aggregates = build_daily_usage_aggregate(morning.date())

    assert len(aggregates) == 1
    aggregate = aggregates[0]
    assert aggregate.organization == organization
    assert aggregate.reader_session_count == 1, "la session du matin precede l'adhesion"
    assert aggregate.page_view_count == 2, "seules les pages de l'apres-midi comptent"


@pytest.mark.django_db
def test_an_anonymous_session_is_attributed_to_no_organization():
    at = timezone.make_aware(timezone.datetime(2026, 3, 11, 9, 0, 0))
    document = create_document(slug="anonyme-doc")
    create_reader_activity(user=None, document=document, started_at=at, page_views=2)

    assert build_daily_usage_aggregate(at.date()) == []
    assert DailyUsageAggregate.objects.count() == 0
