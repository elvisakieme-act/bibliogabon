"""Une page lue compte une fois, quel que soit le nombre de requêtes.

Le lecteur demande plusieurs représentations d'une même page : son texte, son
image, et des dizaines de tuiles. Le journal les enregistre toutes, et il le
doit : une représentation qui ne journaliserait pas offrirait un chemin de
lecture non tracé, et l'audit ne peut pas dépendre de ce que le client a
demandé. Mais `page_view_count` compte les lignes : sans dédoublonnage, tous
les rapports institutionnels auraient été multipliés d'autant.

**Une contrainte d'unicité tient désormais la règle en base** — une ligne par
(session, page). Le dédoublonnage à l'agrégation n'est donc plus la première
barrière, mais il reste nécessaire pour un cas que la contrainte ne peut pas
couvrir : `PageAccessLog.page` passe à `NULL` quand une réingestion supprime
les pages, et PostgreSQL considère les NULL comme distincts. Ces lignes
gardent leur `page_number`, et c'est sur lui que porte le dédoublonnage.
"""

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
from document_reader.models import PageAccessLog


def orphaned_duplicate(session, page_number, at):
    """Une seconde ligne pour la même page, après qu'une réingestion l'a supprimée.

    C'est le seul cas où un doublon peut exister : la contrainte d'unicité
    porte sur (session, page), et une page supprimée laisse `page` à `NULL`,
    que PostgreSQL considère comme distinct d'un autre `NULL`.
    """
    return PageAccessLog.objects.create(
        session=session,
        page=None,
        user=session.user,
        document=session.document,
        page_number=page_number,
        accessed_at=at,
        client_ip=session.client_ip,
        user_agent=session.user_agent,
    )


@pytest.fixture
def reading(db):
    at = timezone.make_aware(timezone.datetime(2026, 3, 10, 9, 0, 0))
    user = create_user(email="dedoublonnage@example.ga")
    organization = create_organization(slug="uss")
    create_active_membership(user, organization, starts_at=at - timezone.timedelta(days=1))
    document = create_document(slug="dedoublonnage", access_model="subscription")
    session = create_reader_activity(user=user, document=document, started_at=at, page_views=3)
    return at, session


@pytest.mark.django_db
def test_the_database_refuses_a_second_row_for_the_same_page(reading):
    """La première barrière est la contrainte, pas le code.

    Le lecteur tuilé demande des dizaines d'images d'une même page : sans
    elle, la règle « une ligne par page lue » ne tiendrait qu'à la faveur du
    code, et céderait à la première écriture concurrente.
    """
    from django.db import IntegrityError, transaction

    at, session = reading
    existing = PageAccessLog.objects.filter(session=session, page_number=1).get()

    with pytest.raises(IntegrityError), transaction.atomic():
        PageAccessLog.objects.bulk_create(
            [
                PageAccessLog(
                    session=session,
                    page=existing.page,
                    user=session.user,
                    document=session.document,
                    page_number=1,
                    accessed_at=at + timezone.timedelta(seconds=1),
                )
            ]
        )


@pytest.mark.django_db
def test_orphaned_duplicates_still_count_as_one_view(reading):
    """Le cas que la contrainte ne peut pas couvrir.

    Une réingestion supprime les pages et laisse les lignes de journal avec
    `page` à `NULL` — PostgreSQL les considère alors comme distinctes. Sans le
    dédoublonnage à l'agrégation, un document réingéré gonflerait les rapports
    de son institution, et rien ne le signalerait.
    """
    at, session = reading
    orphaned_duplicate(session, 1, at + timezone.timedelta(seconds=1))
    orphaned_duplicate(session, 2, at + timezone.timedelta(seconds=2))
    orphaned_duplicate(session, 3, at + timezone.timedelta(seconds=3))

    build_daily_usage_aggregate(at.date())

    assert PageAccessLog.objects.count() == 6, "le journal garde bien les six accès"
    assert DailyUsageAggregate.objects.get().page_view_count == 3


@pytest.mark.django_db
def test_returning_to_a_page_later_in_the_session_does_not_inflate_the_count(reading):
    """Feuilleter n'est pas lire trois fois plus."""
    at, session = reading
    for minute in (20, 40, 60):
        orphaned_duplicate(session, 2, at + timezone.timedelta(minutes=minute))

    build_daily_usage_aggregate(at.date())

    assert DailyUsageAggregate.objects.get().page_view_count == 3


@pytest.mark.django_db
def test_two_sessions_reading_the_same_page_count_twice(reading):
    """Le dédoublonnage ne doit pas effacer une lecture réelle.

    C'est la direction opposée, et elle compte autant : un dédoublonnage trop
    large ferait disparaître l'activité de plusieurs lecteurs d'une même
    institution sur un même document.
    """
    from accounts.models import Organization

    at, session = reading
    other_user = create_user(email="second-lecteur@example.ga")
    # La même organisation, pas une seconde : c'est bien deux lecteurs d'une
    # même institution qu'on veut compter.
    create_active_membership(
        other_user,
        Organization.objects.get(slug="uss"),
        starts_at=at - timezone.timedelta(days=1),
    )
    # Une minute plus tard : la fabrique dérive l'étiquette de version de
    # l'horodatage, et deux versions du même document ne peuvent pas la
    # partager.
    create_reader_activity(
        user=other_user,
        document=session.document,
        started_at=at + timezone.timedelta(minutes=1),
        page_views=3,
    )

    build_daily_usage_aggregate(at.date())

    total = sum(a.page_view_count for a in DailyUsageAggregate.objects.all())
    assert total == 6


@pytest.mark.django_db
def test_distinct_pages_still_count_separately(reading):
    at, session = reading

    build_daily_usage_aggregate(at.date())

    assert DailyUsageAggregate.objects.get().page_view_count == 3
