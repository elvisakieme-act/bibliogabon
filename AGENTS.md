# Repository Guidelines

## Project Structure & Module Organization

This repository contains the BiblioGABON Django backend and product planning documents. Backend code lives in `backend/`, with Django apps such as `accounts`, `catalog`, `document_reader`, `billing`, `operations`, and `analytics`. Technical specs and implementation plans live under `docs/`; operational runbooks live under `docs/operations/`.

## Build, Test, And Development Commands

Run backend commands from `backend/`:

- `.\.venv\Scripts\python.exe -m pytest -q`: run the full test suite.
- `.\.venv\Scripts\python.exe -m pytest api/v1/tests -q`: run the public API V1 tests.
- `.\.venv\Scripts\python.exe manage.py check` (`python manage.py check` when the venv Python is on PATH): run Django system checks.
- `.\.venv\Scripts\python.exe manage.py spectacular --file schema.yml`: export the OpenAPI schema.
- `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`: confirm migrations are committed.
- `.\.venv\Scripts\python.exe manage.py migrate`: apply local migrations.
- `.\.venv\Scripts\python.exe manage.py runserver`: start the local Django server.
- `cd frontend && npm install`: install frontend dependencies.
- `cd frontend && npm run dev`: start the reader-facing web app.
- `cd frontend && npm run build`: type-check and build the frontend.
- `cd frontend && npm run test`: run frontend tests.

## Coding Style & Naming Conventions

Use Python 3.12 and Django conventions. Keep models, services, admin classes, URLs, and tests close to their app. Use 4-space indentation, descriptive domain names, and small service functions for cross-model behavior. Keep secrets and environment-specific values in environment variables and document them in `backend/.env.example`.

## Testing Guidelines

Use pytest and pytest-django. Add tests with every behavior change, and prefer tests that exercise real model/service behavior. Keep app tests under `backend/<app>/tests/`. Cover success, denial, idempotency, privacy, and boundary conditions for reader access, billing, operations, analytics, and launch hardening.

## Commit & Pull Request Guidelines

Use short imperative commit messages with a conventional prefix, such as `feat: add health endpoint`, `fix: harden production settings`, or `docs: add backup runbook`. Pull requests should include a concise summary, linked issue when available, test results, migration notes, and screenshots or sample API responses for user-facing behavior.

## Security & Configuration Tips

Never commit secrets, raw document files, payment credentials, or production database URLs. Production settings must use `DJANGO_ENV=production`, `DJANGO_DEBUG=False`, explicit allowed hosts, HTTPS CSRF trusted origins, secure cookies, and private document storage.
