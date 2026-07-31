import pytest
from django.test import override_settings


ALLOWED_ORIGIN = "http://127.0.0.1:5173"
DISALLOWED_ORIGIN = "https://untrusted.example"


@pytest.mark.django_db
@override_settings(CORS_ALLOWED_ORIGINS=[ALLOWED_ORIGIN])
def test_allowed_origin_receives_cors_headers(client):
    response = client.get("/health/", HTTP_ORIGIN=ALLOWED_ORIGIN)

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN
    assert "Origin" in response.headers["Vary"]
    assert "PATCH" in response.headers["Access-Control-Allow-Methods"]
    assert "Authorization" in response.headers["Access-Control-Allow-Headers"]
    assert response.headers["Access-Control-Max-Age"] == "86400"


@pytest.mark.django_db
@override_settings(CORS_ALLOWED_ORIGINS=[ALLOWED_ORIGIN])
def test_disallowed_origin_receives_no_cors_headers(client):
    response = client.get("/health/", HTTP_ORIGIN=DISALLOWED_ORIGIN)

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers


@override_settings(CORS_ALLOWED_ORIGINS=[ALLOWED_ORIGIN])
def test_allowed_preflight_returns_no_content_with_cors_headers(client):
    response = client.options(
        "/health/",
        HTTP_ORIGIN=ALLOWED_ORIGIN,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="PATCH",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
    )

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN
    assert "PATCH" in response.headers["Access-Control-Allow-Methods"]
    assert "Authorization" in response.headers["Access-Control-Allow-Headers"]


@override_settings(CORS_ALLOWED_ORIGINS=[ALLOWED_ORIGIN])
def test_disallowed_preflight_is_not_treated_as_allowed(client):
    response = client.options(
        "/health/",
        HTTP_ORIGIN=DISALLOWED_ORIGIN,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="PATCH",
    )

    assert response.status_code != 204
    assert "Access-Control-Allow-Origin" not in response.headers
