# BiblioGABON Launch Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden BiblioGABON backend configuration, health checks, logging, and launch runbooks for a controlled first deployment.

**Architecture:** Keep launch-readiness code in the existing Django `config` package. Add small framework-native helpers for environment parsing, production validation, logging configuration, and health checks; document manual operations under `docs/operations/`.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, pytest, pytest-django, SQLite local/test fallback, PostgreSQL production target, S3-compatible private document storage.

## Global Constraints

- Environment-specific values must come from environment variables, not hard-coded secrets.
- Production mode must fail closed for dangerous defaults.
- The backend must not allow `DEBUG=True`, a development secret key, or missing host configuration when explicitly running in production.
- A health endpoint may confirm that Django is running and the database can answer a lightweight query.
- The health endpoint must not disclose secrets, stack traces, database credentials, storage keys, user data, document metadata, or payment details.
- Prefer simple framework-native Django code over new dependencies.
- Development must remain easy: SQLite fallback, local hosts, non-secure cookies, and the current local test commands continue to work.
- Logs should include timestamp, level, logger name, and message.
- Avoid logging personal reading data, payment metadata, secrets, request bodies, document text, signed URLs, raw storage keys, or user emails from this slice.
- Runbooks must describe manual, auditable procedures rather than running destructive commands automatically.
- Do not provision hosting, create Docker or CI/CD pipelines, integrate Sentry, Prometheus, Grafana, Celery, Redis, or automate destructive backup/restore scripts.

---

## File Structure

```text
AGENTS.md
backend/
  .env.example
  config/
    env.py
    health.py
    logconfig.py
    settings.py
    urls.py
    tests/
      __init__.py
      test_env.py
      test_health.py
      test_logging.py
      test_operations_docs.py
  pyproject.toml
  pytest.ini
docs/
  operations/
    backup-and-restore.md
    deployment-checklist.md
    incident-response.md
```

---

### Task 1: Environment Helpers And Production Validation

**Files:**
- Create: `backend/config/env.py`
- Create: `backend/config/tests/__init__.py`
- Create: `backend/config/tests/test_env.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/pytest.ini`

**Interfaces:**
- Produces `env_bool(name: str, default: bool = False) -> bool`.
- Produces `env_int(name: str, default: int) -> int`.
- Produces `env_list(name: str, default: str = "") -> list[str]`.
- Produces `env_required(name: str) -> str`.
- Produces `validate_django_env(value: str) -> str`.
- Produces `validate_production_settings(...) -> None`.
- Produces settings values `DJANGO_ENV`, `CSRF_TRUSTED_ORIGINS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, and `CSRF_COOKIE_SECURE`.

- [ ] **Step 1: Write failing environment helper tests**

Create `backend/config/tests/test_env.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `.\.venv\Scripts\python.exe -m pytest config/tests/test_env.py -q`

Expected: FAIL during import because `config.env` does not exist.

- [ ] **Step 3: Implement environment helpers**

Create `backend/config/env.py`:

```python
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
```

- [ ] **Step 4: Wire helpers into Django settings**

Modify `backend/config/settings.py`:

```python
from pathlib import Path
import os

import dj_database_url

from config.env import env_bool, env_int, env_list, validate_django_env, validate_production_settings
```

Replace existing environment parsing with:

```python
DJANGO_ENV = validate_django_env(os.getenv("DJANGO_ENV", "development"))
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = env_bool("DJANGO_DEBUG", default=DJANGO_ENV != "production")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=DJANGO_ENV == "production")
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", default=DJANGO_ENV == "production")
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", default=DJANGO_ENV == "production")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
```

Replace `READER_SESSION_TTL_MINUTES` with:

```python
READER_SESSION_TTL_MINUTES = env_int("READER_SESSION_TTL_MINUTES", 120)
```

Add after cookie settings:

```python
validate_production_settings(
    django_env=DJANGO_ENV,
    debug=DEBUG,
    secret_key=SECRET_KEY,
    allowed_hosts=ALLOWED_HOSTS,
    csrf_trusted_origins=CSRF_TRUSTED_ORIGINS,
    secure_ssl_redirect=SECURE_SSL_REDIRECT,
    session_cookie_secure=SESSION_COOKIE_SECURE,
    csrf_cookie_secure=CSRF_COOKIE_SECURE,
)
```

- [ ] **Step 5: Register config tests in pytest paths**

Add `"config/tests"` to `backend/pyproject.toml` testpaths and `config/tests` to `backend/pytest.ini` testpaths.

- [ ] **Step 6: Run tests to verify they pass**

Run from `backend`: `.\.venv\Scripts\python.exe -m pytest config/tests/test_env.py -q`

Expected: PASS with 10 tests.

- [ ] **Step 7: Commit**

```bash
git add backend/config/env.py backend/config/tests backend/config/settings.py backend/pyproject.toml backend/pytest.ini
git commit -m "feat: harden django environment settings"
```

---

### Task 2: Health Endpoint

**Files:**
- Create: `backend/config/health.py`
- Create: `backend/config/tests/test_health.py`
- Modify: `backend/config/urls.py`

**Interfaces:**
- Produces `database_is_healthy() -> bool`.
- Produces `health(request) -> JsonResponse`.
- Exposes `GET /health/`.

- [ ] **Step 1: Write failing health endpoint tests**

Create `backend/config/tests/test_health.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `.\.venv\Scripts\python.exe -m pytest config/tests/test_health.py -q`

Expected: FAIL because `/health/` is not routed or `config.health` does not exist.

- [ ] **Step 3: Implement health view**

Create `backend/config/health.py`:

```python
from __future__ import annotations

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


def database_is_healthy() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return False
    return True


@never_cache
@require_GET
def health(request):
    database_status = "ok" if database_is_healthy() else "unavailable"
    status_code = 200 if database_status == "ok" else 503
    payload = {
        "status": "ok" if status_code == 200 else "unavailable",
        "checks": {
            "application": "ok",
            "database": database_status,
        },
    }
    return JsonResponse(payload, status=status_code)
```

- [ ] **Step 4: Route health endpoint**

Modify `backend/config/urls.py`:

```python
from config.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("reader/", include("document_reader.urls")),
    path("search/", include("search_discovery.urls")),
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run from `backend`: `.\.venv\Scripts\python.exe -m pytest config/tests/test_health.py -q`

Expected: PASS with 3 tests.

- [ ] **Step 6: Commit**

```bash
git add backend/config/health.py backend/config/urls.py backend/config/tests/test_health.py
git commit -m "feat: add launch health endpoint"
```

---

### Task 3: Logging Configuration And Environment Example

**Files:**
- Create: `backend/config/logconfig.py`
- Create: `backend/config/tests/test_logging.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Produces `build_logging_config(log_level: str) -> dict`.
- Produces Django setting `LOGGING`.
- Documents launch-hardening environment variables in `backend/.env.example`.

- [ ] **Step 1: Write failing logging tests**

Create `backend/config/tests/test_logging.py`:

```python
from pathlib import Path

from config.logconfig import build_logging_config


def test_build_logging_config_uses_requested_level():
    config = build_logging_config("DEBUG")

    assert config["handlers"]["console"]["level"] == "DEBUG"
    assert config["root"]["level"] == "DEBUG"
    assert config["formatters"]["standard"]["format"] == "%(asctime)s %(levelname)s %(name)s %(message)s"


def test_build_logging_config_falls_back_to_info_for_blank_level():
    config = build_logging_config("")

    assert config["root"]["level"] == "INFO"


def test_env_example_documents_launch_hardening_variables():
    env_example = Path(__file__).resolve().parents[2] / ".env.example"
    text = env_example.read_text(encoding="utf-8")

    required_names = [
        "DJANGO_ENV=",
        "DJANGO_SECRET_KEY=",
        "DJANGO_DEBUG=",
        "DJANGO_ALLOWED_HOSTS=",
        "DJANGO_CSRF_TRUSTED_ORIGINS=",
        "DJANGO_SECURE_SSL_REDIRECT=",
        "DJANGO_SESSION_COOKIE_SECURE=",
        "DJANGO_CSRF_COOKIE_SECURE=",
        "DJANGO_LOG_LEVEL=",
        "DATABASE_URL=",
        "DOCUMENT_STORAGE_BUCKET=",
        "DOCUMENT_STORAGE_KEY_PREFIX=",
        "READER_SESSION_TTL_MINUTES=",
    ]
    for name in required_names:
        assert name in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `.\.venv\Scripts\python.exe -m pytest config/tests/test_logging.py -q`

Expected: FAIL because `config.logconfig` does not exist and `.env.example` is incomplete.

- [ ] **Step 3: Implement logging builder**

Create `backend/config/logconfig.py`:

```python
from __future__ import annotations


VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def build_logging_config(log_level: str) -> dict:
    normalized = (log_level or "INFO").strip().upper()
    if normalized not in VALID_LOG_LEVELS:
        normalized = "INFO"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": normalized,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": normalized,
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": normalized,
                "propagate": False,
            },
        },
    }
```

- [ ] **Step 4: Wire logging into settings**

Modify `backend/config/settings.py`:

```python
from config.logconfig import build_logging_config
```

Add after `DEFAULT_AUTO_FIELD`:

```python
LOGGING = build_logging_config(os.getenv("DJANGO_LOG_LEVEL", "INFO"))
```

- [ ] **Step 5: Update `.env.example`**

Replace `backend/.env.example` content with:

```dotenv
DJANGO_ENV=development
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SESSION_COOKIE_SECURE=False
DJANGO_CSRF_COOKIE_SECURE=False
DJANGO_LOG_LEVEL=INFO
DATABASE_URL=postgres://bibliogabon:bibliogabon@localhost:5432/bibliogabon
DOCUMENT_STORAGE_BUCKET=bibliogabon-private-documents
DOCUMENT_STORAGE_KEY_PREFIX=documents
READER_SESSION_TTL_MINUTES=120
```

- [ ] **Step 6: Run tests to verify they pass**

Run from `backend`: `.\.venv\Scripts\python.exe -m pytest config/tests/test_logging.py -q`

Expected: PASS with 3 tests.

- [ ] **Step 7: Commit**

```bash
git add backend/config/logconfig.py backend/config/settings.py backend/config/tests/test_logging.py backend/.env.example
git commit -m "feat: configure launch logging"
```

---

### Task 4: Operations Runbooks And Contributor Guide

**Files:**
- Create: `backend/config/tests/test_operations_docs.py`
- Create: `docs/operations/deployment-checklist.md`
- Create: `docs/operations/backup-and-restore.md`
- Create: `docs/operations/incident-response.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Produces launch runbooks with concrete manual operator steps.
- Updates `AGENTS.md` to match the current Django backend repository.

- [ ] **Step 1: Write failing operations documentation tests**

Create `backend/config/tests/test_operations_docs.py`:

```python
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("relative_path", "required_phrases"),
    [
        (
            "docs/operations/deployment-checklist.md",
            [
                "python manage.py check",
                "python manage.py migrate",
                "DJANGO_ENV=production",
                "/health/",
                "Rollback",
            ],
        ),
        (
            "docs/operations/backup-and-restore.md",
            [
                "pg_dump",
                "psql",
                "S3-compatible",
                "restore test",
                "private document storage",
            ],
        ),
        (
            "docs/operations/incident-response.md",
            [
                "Triage",
                "Containment",
                "AuditLog",
                "payment",
                "reader access",
            ],
        ),
    ],
)
def test_operations_runbooks_contain_operator_steps(relative_path, required_phrases):
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    for phrase in required_phrases:
        assert phrase in text


def test_agents_guide_matches_current_backend_stack():
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "Django backend" in text
    assert "backend/" in text
    assert "pytest" in text
    assert "python manage.py check" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`: `.\.venv\Scripts\python.exe -m pytest config/tests/test_operations_docs.py -q`

Expected: FAIL because the runbooks do not exist and `AGENTS.md` still describes a planning-only repository.

- [ ] **Step 3: Create deployment checklist**

Create `docs/operations/deployment-checklist.md`:

```markdown
# Deployment Checklist

## Pre-Deploy

- Confirm `DJANGO_ENV=production`.
- Confirm `DJANGO_DEBUG=False`.
- Confirm `DJANGO_SECRET_KEY` is a production secret and is not committed.
- Confirm `DJANGO_ALLOWED_HOSTS` contains the production domain.
- Confirm `DJANGO_CSRF_TRUSTED_ORIGINS` contains the HTTPS origin.
- Confirm secure cookie and SSL redirect variables are enabled.
- Confirm `DATABASE_URL` points to the production PostgreSQL database.
- Confirm private document storage credentials are configured outside Git.

## Verification Commands

Run from `backend/` before release:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Run on the deployment target:

```powershell
python manage.py migrate
python manage.py check --deploy
```

## Smoke Checks

- Request `/health/` and confirm HTTP 200.
- Sign in to Django Admin with a staff account.
- Open one published free document in the reader.
- Run one search query that should return a known published document.
- Confirm new errors are not appearing in application logs.

## Rollback

- Stop the new application process.
- Restore the previous application release directory or service image.
- Repoint the process manager to the previous release.
- Run `/health/` after rollback.
- Record the rollback reason, timestamp, operator, and follow-up action in the incident log.
```

- [ ] **Step 4: Create backup and restore runbook**

Create `docs/operations/backup-and-restore.md`:

```markdown
# Backup And Restore Runbook

## Scope

BiblioGABON launch backups cover PostgreSQL data and S3-compatible private document storage. Backups must be encrypted at rest and access must be limited to operators who can restore service.

## PostgreSQL Backup

Run a manual logical backup before risky releases:

```bash
pg_dump "$DATABASE_URL" --format=custom --file="backup-$(date +%Y%m%d-%H%M%S).dump"
```

Store the dump outside the application server and record the backup filename, timestamp, database name, and operator.

## PostgreSQL Restore

Restore into a clean database first:

```bash
createdb bibliogabon_restore_test
pg_restore --dbname=bibliogabon_restore_test backup-file.dump
psql "$RESTORE_DATABASE_URL" -c "select count(*) from django_migrations;"
```

Only restore production after the restore test succeeds and the service owner approves the downtime window.

## Private Document Storage

Document files live in S3-compatible private document storage. Use the storage provider's versioning, lifecycle, and replication controls when available.

Before a risky migration, snapshot or sync the bucket with a provider-approved command such as:

```bash
aws s3 sync "s3://$DOCUMENT_STORAGE_BUCKET/$DOCUMENT_STORAGE_KEY_PREFIX/" "./storage-backup/" --only-show-errors
```

Do not make raw document files public during backup or restore.

## Restore Test Cadence

Run one restore test before launch and after every backup-process change. The restore test must verify database migrations, a sample catalog record, and a private document object reference.
```

- [ ] **Step 5: Create incident response runbook**

Create `docs/operations/incident-response.md`:

```markdown
# Incident Response Runbook

## Triage

- Record detection time, reporter, environment, and visible user impact.
- Check `/health/` for application and database status.
- Review recent application logs at `ERROR` and `WARNING` levels.
- Check whether the issue affects reader access, search, payment, ingestion, or admin workflows.

## Containment

- For reader access incidents, suspend risky entitlements or publication records through existing admin workflows.
- For payment incidents, stop retrying the affected payment provider path and preserve transaction records.
- For document exposure concerns, disable the affected document or storage prefix before investigating content.
- For staff workflow issues, restrict admin access to essential operators.

## Investigation

- Use `operations.AuditLog` to trace publication decisions, support resolutions, report generation, and sensitive admin actions.
- Preserve relevant logs, request IDs, timestamps, and object IDs.
- Do not paste secrets, payment metadata, raw document text, or personal reading data into incident notes.

## Recovery

- Apply the smallest verified fix.
- Run targeted tests and `/health/`.
- Confirm impacted users or institutions can complete the affected workflow.
- Record the recovery timestamp and verification evidence.

## Follow-Up

- Create a post-incident note with cause, impact, response timeline, and prevention work.
- Add regression tests for code defects.
- Update this runbook when response steps were missing or inaccurate.
```

- [ ] **Step 6: Update contributor guide**

Replace `AGENTS.md` with a current guide:

```markdown
# Repository Guidelines

## Project Structure & Module Organization

This repository contains the BiblioGABON Django backend and product planning documents. Backend code lives in `backend/`, with Django apps such as `accounts`, `catalog`, `document_reader`, `billing`, `operations`, and `analytics`. Technical specs and implementation plans live under `docs/`; operational runbooks live under `docs/operations/`.

## Build, Test, And Development Commands

Run backend commands from `backend/`:

- `.\.venv\Scripts\python.exe -m pytest -q`: run the full test suite.
- `.\.venv\Scripts\python.exe manage.py check`: run Django system checks.
- `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`: confirm migrations are committed.
- `.\.venv\Scripts\python.exe manage.py migrate`: apply local migrations.
- `.\.venv\Scripts\python.exe manage.py runserver`: start the local Django server.

## Coding Style & Naming Conventions

Use Python 3.12 and Django conventions. Keep models, services, admin classes, URLs, and tests close to their app. Use 4-space indentation, descriptive domain names, and small service functions for cross-model behavior. Keep secrets and environment-specific values in environment variables and document them in `backend/.env.example`.

## Testing Guidelines

Use pytest and pytest-django. Add tests with every behavior change, and prefer tests that exercise real model/service behavior. Keep app tests under `backend/<app>/tests/`. Cover success, denial, idempotency, privacy, and boundary conditions for reader access, billing, operations, analytics, and launch hardening.

## Commit & Pull Request Guidelines

Use short imperative commit messages with a conventional prefix, such as `feat: add health endpoint`, `fix: harden production settings`, or `docs: add backup runbook`. Pull requests should include a concise summary, linked issue when available, test results, migration notes, and screenshots or sample API responses for user-facing behavior.

## Security & Configuration Tips

Never commit secrets, raw document files, payment credentials, or production database URLs. Production settings must use `DJANGO_ENV=production`, `DJANGO_DEBUG=False`, explicit allowed hosts, HTTPS CSRF trusted origins, secure cookies, and private document storage.
```

- [ ] **Step 7: Run documentation tests**

Run from `backend`: `.\.venv\Scripts\python.exe -m pytest config/tests/test_operations_docs.py -q`

Expected: PASS with 4 tests.

- [ ] **Step 8: Run full verification**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate
```

Run from repo root:

```powershell
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 9: Commit**

```bash
git add AGENTS.md docs/operations backend/config/tests/test_operations_docs.py
git commit -m "docs: add launch operations runbooks"
```
