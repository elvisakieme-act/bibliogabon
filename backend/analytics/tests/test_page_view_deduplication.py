"""Une page lue compte une fois, quel que soit le nombre de requêtes.

Le lecteur demande désormais deux représentations d'une même page : son texte
— avec la position des mots — et son image fidèle. Le journal d'accès
enregistre les deux, et il le doit : une représentation qui ne journaliserait
pas offrirait un chemin de lecture non tracé, et l'audit ne peut pas dépendre
de ce que le client a demandé.

Mais `page_view_count` comptait les lignes du journal. Sans dédoublonnage, tous
les rapports institutionnels auraient doublé — sans erreur, sans alerte, et
sans possibilité de reconstituer les chiffres a posteriori.

Le dédoublonnage porte sur (session, page). Il corrige au passage un défaut
antérieur : un lecteur qui revenait sur une page gonflait le compte de son
institution.
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
from document_processing.models import DocumentPage
from document_reader.models import PageAccessLog


def read_the_same_page_again(session, page_number, at):
    """Ce que fait le lecteur quand il demande l'image après le texte."""
    page = DocumentPage.objects.get(version=session.version, page_number=page_number)
    return PageAccessLog.objects.create(
        session=session,
        page=page,
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
def test_text_and_image_of_one_page_count_as_one_view(reading):
    at, session = reading
    read_the_same_page_again(session, 1, at + timezone.timedelta(seconds=1))
    read_the_same_page_again(session, 2, at + timezone.timedelta(seconds=2))
    read_the_same_page_again(session, 3, at + timezone.timedelta(seconds=3))

    build_daily_usage_aggregate(at.date())

    assert PageAccessLog.objects.count() == 6, "le journal garde bien les six accès"
    assert DailyUsageAggregate.objects.get().page_view_count == 3


@pytest.mark.django_db
def test_returning_to_a_page_later_in_the_session_does_not_inflate_the_count(reading):
    """Feuilleter n'est pas lire trois fois plus."""
    at, session = reading
    for minute in (20, 40, 60):
        read_the_same_page_again(session, 2, at + timezone.timedelta(minutes=minute))

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
