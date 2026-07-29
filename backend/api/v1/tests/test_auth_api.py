import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework.test import APIClient
from drf_spectacular.generators import SchemaGenerator


def bearer(access_token: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {access_token}"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        (
            "application/x-www-form-urlencoded",
            "email=form%40example.ga&password=StrongPass123%21",
        ),
        (
            "multipart/form-data; boundary=BoUnDaRyStRiNg",
            (
                "--BoUnDaRyStRiNg\r\n"
                'Content-Disposition: form-data; name="email"\r\n\r\n'
                "multipart@example.ga\r\n"
                "--BoUnDaRyStRiNg\r\n"
                'Content-Disposition: form-data; name="password"\r\n\r\n'
                "StrongPass123!\r\n"
                "--BoUnDaRyStRiNg--\r\n"
            ),
        ),
    ],
)
def test_registration_rejects_non_json_request_bodies(content_type, body):
    client = APIClient()

    response = client.post(
        "/api/v1/auth/register/",
        data=body,
        content_type=content_type,
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


@pytest.mark.django_db
def test_register_creates_individual_user_and_returns_tokens():
    client = APIClient()

    response = client.post(
        "/api/v1/auth/register/",
        {
            "email": "reader@example.ga",
            "password": "StrongPass123!",
            "display_name": "Reader One",
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    user = get_user_model().objects.get(email="reader@example.ga")
    assert user.account_type == get_user_model().AccountType.INDIVIDUAL
    assert payload["user"] == {
        "id": user.pk,
        "email": "reader@example.ga",
        "display_name": "Reader One",
        "account_type": "individual",
    }
    assert set(payload["tokens"]) == {"access", "refresh"}
    assert "password" not in str(payload).lower()


@pytest.mark.django_db
def test_register_rejects_duplicate_email_with_409():
    User = get_user_model()
    User.objects.create_user(email="reader@example.ga", password="pass")
    client = APIClient()

    response = client.post(
        "/api/v1/auth/register/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_exists"


@pytest.mark.django_db
def test_register_normalizes_create_time_duplicate_email_race_to_409(monkeypatch):
    User = get_user_model()
    client = APIClient()

    def raise_duplicate_email(*args, **kwargs):
        raise IntegrityError("UNIQUE constraint failed: accounts_user.email")

    monkeypatch.setattr(User.objects, "create_user", raise_duplicate_email)

    response = client.post(
        "/api/v1/auth/register/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_exists"


@pytest.mark.django_db
def test_token_login_and_me_endpoint_use_jwt_only():
    User = get_user_model()
    user = User.objects.create_user(
        email="reader@example.ga",
        password="StrongPass123!",
        display_name="Reader One",
    )
    client = APIClient()

    token_response = client.post(
        "/api/v1/auth/token/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )

    assert token_response.status_code == 200
    access = token_response.json()["access"]
    me_response = client.get("/api/v1/me/", **bearer(access))
    assert me_response.status_code == 200
    assert me_response.json()["email"] == user.email


@pytest.mark.django_db
def test_me_endpoint_rejects_anonymous_user():
    client = APIClient()

    response = client.get("/api/v1/me/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] in {"authentication_required", "not_authenticated"}


@pytest.mark.django_db
def test_me_patch_updates_only_allowed_profile_fields():
    client = APIClient()
    register = client.post(
        "/api/v1/auth/register/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )
    access = register.json()["tokens"]["access"]

    response = client.patch(
        "/api/v1/me/",
        {"display_name": "Updated Reader", "account_type": "platform_staff"},
        format="json",
        **bearer(access),
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Reader"
    assert response.json()["account_type"] == "individual"


@pytest.mark.django_db
def test_logout_blacklists_refresh_token():
    client = APIClient()
    register = client.post(
        "/api/v1/auth/register/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )
    access = register.json()["tokens"]["access"]
    refresh = register.json()["tokens"]["refresh"]

    response = client.post(
        "/api/v1/auth/logout/",
        {"refresh": refresh},
        format="json",
        **bearer(access),
    )

    assert response.status_code == 204
    refresh_response = client.post(
        "/api/v1/auth/token/refresh/",
        {"refresh": refresh},
        format="json",
    )
    assert refresh_response.status_code == 401


@pytest.mark.django_db
def test_logout_cannot_blacklist_another_users_refresh_token():
    client = APIClient()
    victim = client.post(
        "/api/v1/auth/register/",
        {"email": "victim@example.ga", "password": "StrongPass123!"},
        format="json",
    ).json()
    attacker = client.post(
        "/api/v1/auth/register/",
        {"email": "attacker@example.ga", "password": "StrongPass123!"},
        format="json",
    ).json()

    response = client.post(
        "/api/v1/auth/logout/",
        {"refresh": victim["tokens"]["refresh"]},
        format="json",
        **bearer(attacker["tokens"]["access"]),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "refresh_token_user_mismatch"
    refresh_response = client.post(
        "/api/v1/auth/token/refresh/",
        {"refresh": victim["tokens"]["refresh"]},
        format="json",
    )
    assert refresh_response.status_code == 200


def test_openapi_schema_documents_auth_and_current_user_endpoints():
    paths = SchemaGenerator().get_schema(request=None, public=True)["paths"]

    expected_operations = {
        "/api/v1/auth/register/": {"post": {"201", "400", "409"}},
        "/api/v1/auth/token/": {"post": {"200", "401"}},
        "/api/v1/auth/token/refresh/": {"post": {"200", "401"}},
        "/api/v1/auth/logout/": {"post": {"204", "400", "403"}},
        "/api/v1/me/": {"get": {"200", "401"}, "patch": {"200", "400", "401"}},
    }

    for path, operations in expected_operations.items():
        for method, response_codes in operations.items():
            operation = paths[path][method]
            assert response_codes <= set(operation["responses"])
            if method in {"post", "patch"}:
                assert "requestBody" in operation
