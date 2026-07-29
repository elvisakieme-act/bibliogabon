# BiblioGABON Launch Hardening Design

## Purpose

This slice prepares the BiblioGABON backend for a controlled first deployment. It hardens configuration, adds a simple health surface, improves runtime logging, and documents operational procedures for deployment, backup, restore, and incident handling.

It does not provision hosting, create Docker or CI/CD pipelines, integrate Sentry, Prometheus, Grafana, Celery, Redis, or automate destructive backup/restore scripts.

## Product Rules

Launch readiness must reduce avoidable production risk without locking the project into a hosting provider. Environment-specific values must come from environment variables, not hard-coded secrets.

Production mode must fail closed for dangerous defaults. The backend must not allow `DEBUG=True`, a development secret key, or missing host configuration when explicitly running in production.

Operational checks must be safe to expose to infrastructure monitors. A health endpoint may confirm that Django is running and the database can answer a lightweight query, but it must not disclose secrets, stack traces, database credentials, storage keys, user data, document metadata, or payment details.

## Architecture

Keep the work inside existing `backend/config` unless a small dedicated app is necessary. Prefer simple framework-native Django code over new dependencies.

Core components:

- configuration helpers for boolean, integer, list, and required environment values;
- production-aware Django settings for security headers, cookies, CSRF, host validation, and logging;
- `/health/` endpoint returning a compact JSON status;
- runbooks under `docs/operations/` for deploy, backup, restore, and incident response;
- updated contributor guidance if repository metadata is stale.

The health endpoint should return HTTP 200 when application and database checks pass, and HTTP 503 when the database check fails. It should be unauthenticated but intentionally minimal.

## Configuration Hardening

Add explicit environment variables:

- `DJANGO_ENV`: `development`, `test`, or `production`;
- `DJANGO_SECRET_KEY`;
- `DJANGO_DEBUG`;
- `DJANGO_ALLOWED_HOSTS`;
- `DJANGO_CSRF_TRUSTED_ORIGINS`;
- `DJANGO_SECURE_SSL_REDIRECT`;
- `DJANGO_SESSION_COOKIE_SECURE`;
- `DJANGO_CSRF_COOKIE_SECURE`;
- `DJANGO_LOG_LEVEL`;
- `DATABASE_URL`;
- existing document storage and reader session variables.

In production, require a non-development `DJANGO_SECRET_KEY`, at least one allowed host, `DEBUG=False`, secure cookies, and explicit CSRF trusted origins for browser-facing domains.

Development must remain easy: SQLite fallback, local hosts, non-secure cookies, and the current local test commands continue to work.

## Logging

Configure console logging through Django `LOGGING`. Logs should include timestamp, level, logger name, and message. The default level comes from `DJANGO_LOG_LEVEL`.

Avoid logging personal reading data, payment metadata, secrets, request bodies, document text, signed URLs, raw storage keys, or user emails from this slice.

## Operations Documentation

Create concise runbooks:

- `docs/operations/deployment-checklist.md`;
- `docs/operations/backup-and-restore.md`;
- `docs/operations/incident-response.md`;

These documents should describe manual, auditable procedures rather than running destructive commands automatically. Backup guidance should cover PostgreSQL and S3-compatible private document storage at a process level, including restore testing.

## Testing

Use pytest and pytest-django. Tests must prove:

- development settings still load with safe local defaults;
- production settings reject dangerous defaults;
- list and boolean environment parsing behaves predictably;
- `/health/` returns HTTP 200 when the database responds;
- `/health/` returns HTTP 503 for database check failure;
- health payloads contain no secret or user/document/payment data;
- logging settings are configured from `DJANGO_LOG_LEVEL`;
- required operational docs exist and contain concrete operator steps.

## Out Of Scope

- Real deployment to a VM or cloud provider.
- Docker Compose, Kubernetes, Terraform, or CI/CD.
- External monitoring, alerting, Sentry, Prometheus, or Grafana.
- Automated backup deletion or restore scripts.
- Celery or Redis production operations.
- Public status page.
- Load testing and performance tuning.
