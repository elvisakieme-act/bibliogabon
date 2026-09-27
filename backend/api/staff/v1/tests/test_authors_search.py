from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import (
    AcademicDomain,
    Author,
    Document,
    DocumentAuthor,
)


@pytest.fixture
def registry(db):
    published_author = Author.objects.create(
        display_name="Aline NZE", normalized_name="nze aline", affiliation="UOB"
    )
    unpublished_author = Author.objects.create(
        display_name="Brice ONDO", normalized_name="ondo brice", affiliation="USTM"
    )
    domain = AcademicDomain.objects.create(name="Droit", slug="droit-auteurs")
    document = Document.objects.create(
        title="Document publie",
        slug="document-publie-auteurs",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )
    DocumentAuthor.objects.create(
        document=document, author=published_author, role=DocumentAuthor.Role.AUTHOR, position=1
    )
    return {"published": published_author, "unpublished": unpublished_author}


def make_user(email: str, account_type: str) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type
    )


@pytest.fixture
def api():
    return APIClient()


def authenticate(client, user):
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_an_author_who_has_never_been_published_is_findable(api, registry):
    """L'endpoint public ne liste que les auteurs de documents publiés. Au
    moment du dépôt, c'est exactement le cas qui manque."""
    client = authenticate(api, make_user("prof@bg.ga", User.AccountType.TEACHER_AUTHOR))

    response = client.get(reverse("api-staff-v1:author-list"))

    assert response.status_code == 200
    names = [row["display_name"] for row in response.json()["results"]]
    assert "Brice ONDO" in names
    assert "Aline NZE" in names


@pytest.mark.django_db
def test_the_search_filters_on_the_displayed_name(api, registry):
    client = authenticate(api, make_user("prof2@bg.ga", User.AccountType.TEACHER_AUTHOR))

    response = client.get(reverse("api-staff-v1:author-list"), {"q": "ondo"})

    names = [row["display_name"] for row in response.json()["results"]]
    assert names == ["Brice ONDO"]


@pytest.mark.django_db
def test_a_reader_is_refused(api, registry):
    client = authenticate(api, make_user("lecteur@bg.ga", User.AccountType.INDIVIDUAL))

    response = client.get(reverse("api-staff-v1:author-list"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_an_anonymous_visitor_is_refused(api, registry):
    response = api.get(reverse("api-staff-v1:author-list"))

    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_the_payload_carries_identity_only(api, registry):
    """Un registre d'auteurs n'a pas à livrer les adresses de contact ni le
    compte utilisateur rattaché : l'écran a besoin d'un nom et d'un id."""
    client = authenticate(api, make_user("prof3@bg.ga", User.AccountType.TEACHER_AUTHOR))

    response = client.get(reverse("api-staff-v1:author-list"))

    row = response.json()["results"][0]
    assert set(row) == {"id", "display_name", "author_type", "affiliation"}
