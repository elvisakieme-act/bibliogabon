from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User


def make_user(email: str, account_type: str, **extra) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type, **extra
    )


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_an_anonymous_caller_is_not_authenticated(api):
    response = api.get(reverse("api-staff-v1:index"))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("account_type", "allowed"),
    [
        (User.AccountType.INDIVIDUAL, False),
        (User.AccountType.TEACHER_AUTHOR, True),
        (User.AccountType.ORGANIZATION_ADMIN, True),
        (User.AccountType.CONTENT_ADMIN, True),
        (User.AccountType.PLATFORM_STAFF, True),
    ],
)
def test_the_staff_api_floor_refuses_a_reader(api, account_type, allowed):
    """Le plancher laisse entrer qui a un rôle de back-office ; chaque
    endpoint resserre ensuite."""
    api.force_authenticate(make_user(f"{account_type}@example.ga", account_type))

    response = api.get(reverse("api-staff-v1:index"))

    assert response.status_code == (200 if allowed else 403)
    if not allowed:
        assert response.json()["error"]["code"] == "permission_denied"


@pytest.mark.django_db
def test_a_refusal_uses_the_standard_error_envelope(api):
    api.force_authenticate(make_user("etudiant@example.ga", User.AccountType.INDIVIDUAL))

    payload = api.get(reverse("api-staff-v1:index")).json()

    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"code", "message", "field_errors"}


@pytest.mark.django_db
def test_the_staff_schema_documents_staff_paths(api):
    api.force_authenticate(make_user("mod@bibliogabon.ga", User.AccountType.CONTENT_ADMIN))

    response = api.get(reverse("api-staff-v1-schema"), {"format": "json"})

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert any(path.startswith("/api/staff/v1/") for path in paths), paths


@pytest.mark.django_db
def test_the_public_schema_contains_no_staff_path(api):
    """Deux publics, deux contrats. Le contrat public promet de ne jamais
    révéler qu'un document non publié existe ; l'API staff existe pour les
    montrer. Une fuite dans le schéma public est l'échec à ne pas commettre."""
    response = api.get(reverse("api-v1-schema"), {"format": "json"})

    assert response.status_code == 200
    leaked = [path for path in response.json()["paths"] if path.startswith("/api/staff")]
    assert leaked == [], leaked


@pytest.mark.django_db
def test_the_staff_schema_contains_no_public_path(api):
    api.force_authenticate(make_user("mod2@bibliogabon.ga", User.AccountType.CONTENT_ADMIN))

    response = api.get(reverse("api-staff-v1-schema"), {"format": "json"})

    stray = [path for path in response.json()["paths"] if not path.startswith("/api/staff/v1/")]
    assert stray == [], stray


@pytest.mark.django_db
def test_the_index_announces_the_upload_bounds(settings):
    """L'écran refuse un fichier hors bornes avant d'ouvrir une requête, ce
    qui demande qu'il connaisse les bornes. Les recopier côté client les
    ferait dériver de la configuration réelle."""
    settings.DOCUMENT_UPLOAD_MAX_BYTES = 12345
    settings.DOCUMENT_UPLOAD_ACCEPTED_MIME_TYPES = ["application/pdf", "application/epub+zip"]
    client = APIClient()
    client.force_authenticate(
        user=User.objects.create_user(
            email="index@bibliogabon.ga",
            password="passphrase",
            account_type=User.AccountType.CONTENT_ADMIN,
        )
    )

    payload = client.get(reverse("api-staff-v1:index")).json()

    assert payload["upload"] == {
        "max_bytes": 12345,
        "accepted_mime_types": ["application/pdf", "application/epub+zip"],
    }
