import pytest
from django.core.exceptions import ImproperlyConfigured

from config.env import (
    env_bool,
    env_int,
    env_list,
    env_required,
    validate_django_env,
    validate_production_settings,
)


def test_env_bool_parses_common_values(monkeypatch):
    monkeypatch.setenv("FEATURE_ON", "true")
    monkeypatch.setenv("FEATURE_OFF", "0")

    assert env_bool("FEATURE_ON") is True
    assert env_bool("FEATURE_OFF", default=True) is False


def test_env_bool_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAG", "perhaps")

    with pytest.raises(ImproperlyConfigured):
        env_bool("FEATURE_FLAG")


def test_env_int_parses_integer_and_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("READER_MINUTES", "45")
    monkeypatch.setenv("BAD_INT", "forty-five")

    assert env_int("READER_MINUTES", default=120) == 45
    with pytest.raises(ImproperlyConfigured):
        env_int("BAD_INT", default=120)


def test_env_list_trims_empty_items(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "localhost, 127.0.0.1, , bibliogabon.ga ")

    assert env_list("DJANGO_ALLOWED_HOSTS") == ["localhost", "127.0.0.1", "bibliogabon.ga"]


def test_env_required_rejects_missing_value(monkeypatch):
    monkeypatch.delenv("MISSING_SECRET", raising=False)

    with pytest.raises(ImproperlyConfigured):
        env_required("MISSING_SECRET")


def test_validate_django_env_accepts_known_modes_and_rejects_unknown_mode():
    assert validate_django_env("production") == "production"

    with pytest.raises(ImproperlyConfigured):
        validate_django_env("staging")


def test_validate_production_settings_rejects_debug_mode():
    with pytest.raises(ImproperlyConfigured):
        validate_production_settings(
            django_env="production",
            debug=True,
            secret_key="prod-secret-key",
            allowed_hosts=["bibliogabon.ga"],
            csrf_trusted_origins=["https://bibliogabon.ga"],
            secure_ssl_redirect=True,
            session_cookie_secure=True,
            csrf_cookie_secure=True,
        )


def test_validate_production_settings_rejects_development_secret_key():
    with pytest.raises(ImproperlyConfigured):
        validate_production_settings(
            django_env="production",
            debug=False,
            secret_key="dev-only-secret-key",
            allowed_hosts=["bibliogabon.ga"],
            csrf_trusted_origins=["https://bibliogabon.ga"],
            secure_ssl_redirect=True,
            session_cookie_secure=True,
            csrf_cookie_secure=True,
        )


def test_validate_production_settings_rejects_local_allowed_hosts():
    with pytest.raises(ImproperlyConfigured):
        validate_production_settings(
            django_env="production",
            debug=False,
            secret_key="prod-secret-key",
            allowed_hosts=["localhost", "127.0.0.1"],
            csrf_trusted_origins=["https://bibliogabon.ga"],
            secure_ssl_redirect=True,
            session_cookie_secure=True,
            csrf_cookie_secure=True,
        )


def test_validate_production_settings_accepts_hardened_values():
    validate_production_settings(
        django_env="production",
        debug=False,
        secret_key="prod-secret-key",
        allowed_hosts=["bibliogabon.ga"],
        csrf_trusted_origins=["https://bibliogabon.ga"],
        secure_ssl_redirect=True,
        session_cookie_secure=True,
        csrf_cookie_secure=True,
    )
