import pytest


@pytest.mark.django_db
def test_health_endpoint_returns_ok_when_database_responds(client):
    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "application": "ok",
            "database": "ok",
        },
    }


@pytest.mark.django_db
def test_health_endpoint_returns_503_when_database_check_fails(client, monkeypatch):
    monkeypatch.setattr("config.health.database_is_healthy", lambda: False)

    response = client.get("/health/")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {
            "application": "ok",
            "database": "unavailable",
        },
    }


@pytest.mark.django_db
def test_health_payload_contains_no_sensitive_domain_data(client):
    response = client.get("/health/")
    payload_text = response.content.decode("utf-8").lower()

    forbidden_terms = [
        "secret",
        "password",
        "database_url",
        "storage_key",
        "session_key",
        "email",
        "document",
        "payment",
        "traceback",
    ]
    for term in forbidden_terms:
        assert term not in payload_text
