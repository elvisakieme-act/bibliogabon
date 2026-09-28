import os
import subprocess
import sys
from pathlib import Path

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


SETTINGS_ENVIRONMENT_NAMES = [
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "CELERY_TASK_ALWAYS_EAGER",
    "DATABASE_URL",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_CSRF_COOKIE_SECURE",
    "DJANGO_DEBUG",
    "DJANGO_ENV",
    "DJANGO_SECRET_KEY",
    "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SESSION_COOKIE_SECURE",
    "DOCUMENT_PAGE_IMAGE_WIDTH",
    "DOCUMENT_STORAGE_BACKEND",
    "DOCUMENT_STORAGE_ENDPOINT_URL",
    "OCR_LANGUAGES",
    "OCR_MIN_CHARACTERS",
]


DEFAULT_DEVELOPMENT_SIGNING_SECRET = "dev-only-secret-key-for-local-jwt-signing-2026"


def import_default_development_settings():
    env = os.environ.copy()
    for name in SETTINGS_ENVIRONMENT_NAMES:
        env.pop(name, None)
    # Le processus enfant charge `backend/.env` comme tout démarrage réel ; le
    # neutraliser est nécessaire pour observer la configuration *par défaut*,
    # qui est ce que ce test mesure.
    env["DJANGO_ENV_FILE"] = ""
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from config.settings import SECRET_KEY; print(len(SECRET_KEY.encode()))",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_default_development_signing_secret_is_long_enough_for_jwt():
    result = import_default_development_settings()

    assert result.returncode == 0, result.stderr
    assert int(result.stdout) >= 32


def test_validate_production_settings_rejects_default_development_signing_secret():
    with pytest.raises(ImproperlyConfigured):
        validate_production_settings(
            django_env="production",
            debug=False,
            secret_key=DEFAULT_DEVELOPMENT_SIGNING_SECRET,
            allowed_hosts=["bibliogabon.ga"],
            csrf_trusted_origins=["https://bibliogabon.ga"],
            secure_ssl_redirect=True,
            session_cookie_secure=True,
            csrf_cookie_secure=True,
        )


def import_production_settings(**environment):
    env = os.environ.copy()
    for name in SETTINGS_ENVIRONMENT_NAMES:
        env.pop(name, None)
    env.update(
        {
            "DJANGO_ENV": "production",
            "DJANGO_SECRET_KEY": "a-production-secret-key",
            "DJANGO_DEBUG": "False",
            "DJANGO_ALLOWED_HOSTS": "bibliogabon.ga",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://bibliogabon.ga",
            "DJANGO_SECURE_SSL_REDIRECT": "True",
            "DJANGO_SESSION_COOKIE_SECURE": "True",
            "DJANGO_CSRF_COOKIE_SECURE": "True",
            "DATABASE_URL": "postgres://bibliogabon:secret@localhost:5432/bibliogabon",
            "CELERY_BROKER_URL": "redis://localhost:6379/0",
            "DOCUMENT_STORAGE_BACKEND": "s3",
            **environment,
        }
    )
    return subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_settings_import_with_valid_configuration():
    result = import_production_settings()

    assert result.returncode == 0, result.stderr


def test_production_settings_import_rejects_missing_database_url():
    result = import_production_settings(DATABASE_URL="")

    assert result.returncode != 0
    assert "DATABASE_URL is required in production" in result.stderr


def test_production_settings_import_rejects_non_https_csrf_trusted_origin():
    result = import_production_settings(DJANGO_CSRF_TRUSTED_ORIGINS="http://bibliogabon.ga")

    assert result.returncode != 0
    assert "DJANGO_CSRF_TRUSTED_ORIGINS must use HTTPS in production" in result.stderr


def test_production_settings_import_rejects_missing_celery_broker():
    result = import_production_settings(CELERY_BROKER_URL="")

    assert result.returncode != 0
    assert "CELERY_BROKER_URL is required in production" in result.stderr


def test_production_settings_import_rejects_filesystem_document_storage():
    result = import_production_settings(DOCUMENT_STORAGE_BACKEND="filesystem")

    assert result.returncode != 0
    assert "DOCUMENT_STORAGE_BACKEND must be s3 in production" in result.stderr


def test_production_settings_import_rejects_unknown_document_storage_backend():
    result = import_production_settings(DOCUMENT_STORAGE_BACKEND="dropbox")

    assert result.returncode != 0
    assert "DOCUMENT_STORAGE_BACKEND must be" in result.stderr


def import_development_settings_value(expression, **environment):
    env = os.environ.copy()
    for name in SETTINGS_ENVIRONMENT_NAMES:
        env.pop(name, None)
    env.update(environment)
    return subprocess.run(
        [sys.executable, "-c", f"from config.settings import *; print({expression})"],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_development_defaults_run_tasks_inline_without_a_broker():
    result = import_development_settings_value("CELERY_TASK_ALWAYS_EAGER")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


def test_development_defaults_to_filesystem_document_storage():
    result = import_development_settings_value("DOCUMENT_STORAGE_BACKEND")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "filesystem"


def test_pipeline_tuning_values_come_from_the_environment():
    result = import_development_settings_value(
        "(DOCUMENT_PAGE_IMAGE_WIDTH, OCR_LANGUAGES, OCR_MIN_CHARACTERS)",
        DOCUMENT_PAGE_IMAGE_WIDTH="900",
        OCR_LANGUAGES="fra+eng",
        OCR_MIN_CHARACTERS="40",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "(900, 'fra+eng', 40)"


def test_pipeline_tuning_values_have_safe_defaults():
    result = import_development_settings_value(
        "(DOCUMENT_PAGE_IMAGE_WIDTH, OCR_LANGUAGES, OCR_MIN_CHARACTERS)"
    )

    assert result.returncode == 0, result.stderr
    # 2480 px : 300 ppp pour une A4, la norme d'archivage. Le tuilage IIIF
    # rend ce choix peu coûteux pour le lecteur, qui ne télécharge que les
    # tuiles qu'il regarde. Changer cette valeur oblige à réingérer — les
    # tuiles et leur `info.json` en dépendent — d'où ce verrou.
    assert result.stdout.strip() == "(2480, 'fra', 20)"
