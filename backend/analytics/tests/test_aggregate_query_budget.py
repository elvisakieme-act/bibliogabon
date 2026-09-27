import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from analytics.services import build_daily_usage_aggregate
from analytics.tests.factories import (
    create_active_membership,
    create_document,
    create_organization,
    create_reader_activity,
    create_user,
)


def seed_day(*, readers: int, pages: int, at, slug: str):
    organization = create_organization(slug=slug)
    document = create_document(slug=f"doc-{slug}")
    for index in range(readers):
        user = create_user(email=f"{slug}-{index}@example.ga")
        create_active_membership(user, organization, starts_at=at - timezone.timedelta(days=1))
        create_reader_activity(
            user=user,
            document=document,
            started_at=at + timezone.timedelta(seconds=index),
            page_views=pages,
        )


@pytest.mark.django_db
def test_aggregation_cost_does_not_grow_with_the_volume_of_activity():
    """L'attribution d'une activite a une organisation interrogeait la base
    par activite : 2 requetes chacune, soit 100 000 requetes pour une
    journee a 50 000 pages lues, multipliees par 30 pour un rapport
    mensuel. Le cout doit etre constant."""
    at = timezone.make_aware(timezone.datetime(2026, 1, 15, 10, 0, 0))
    seed_day(readers=2, pages=2, at=at, slug="budget-petit")
    with CaptureQueriesContext(connection) as small:
        build_daily_usage_aggregate(at.date())

    later = at + timezone.timedelta(days=1)
    seed_day(readers=10, pages=10, at=later, slug="budget-grand")
    with CaptureQueriesContext(connection) as large:
        build_daily_usage_aggregate(later.date())

    # 6 activites contre 110 : un cout proportionnel se verrait immediatement.
    assert len(large) <= len(small) + 12, (
        f"cout proportionnel au volume : {len(small)} requetes pour 6 activites, "
        f"{len(large)} pour 110"
    )
