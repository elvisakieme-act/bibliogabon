from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured


VALID_DJANGO_ENVS = {"development", "test", "production"}
TRUTHY_VALUES = {"1", "true", "yes", "on"}
FALSY_VALUES = {"0", "false", "no", "off"}
DEVELOPMENT_SECRET_KEYS = {"", "dev-only-secret-key", "change-me-in-production"}
LOCAL_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in TRUTHY_VALUES:
        return True
    if normalized in FALSY_VALUES:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean value")


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer") from exc


def env_list(name: str, default: str = "") -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def env_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"{name} is required")
    return value


def validate_django_env(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in VALID_DJANGO_ENVS:
        raise ImproperlyConfigured("DJANGO_ENV must be development, test, or production")
    return normalized


def validate_production_settings(
    *,
    django_env: str,
    debug: bool,
    secret_key: str,
    allowed_hosts: list[str],
    csrf_trusted_origins: list[str],
    secure_ssl_redirect: bool,
    session_cookie_secure: bool,
    csrf_cookie_secure: bool,
) -> None:
    if django_env != "production":
        return
    if debug:
        raise ImproperlyConfigured("DJANGO_DEBUG must be False in production")
    if secret_key.strip() in DEVELOPMENT_SECRET_KEYS:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a production value")
    if not allowed_hosts or "*" in allowed_hosts:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must contain explicit production hosts")
    if all(host in LOCAL_ALLOWED_HOSTS for host in allowed_hosts):
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must include a non-local production host")
    if not csrf_trusted_origins:
        raise ImproperlyConfigured("DJANGO_CSRF_TRUSTED_ORIGINS is required in production")
    if not secure_ssl_redirect:
        raise ImproperlyConfigured("DJANGO_SECURE_SSL_REDIRECT must be True in production")
    if not session_cookie_secure:
        raise ImproperlyConfigured("DJANGO_SESSION_COOKIE_SECURE must be True in production")
    if not csrf_cookie_secure:
        raise ImproperlyConfigured("DJANGO_CSRF_COOKIE_SECURE must be True in production")
