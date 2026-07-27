# BiblioGABON Secure Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first secure reader foundation with authenticated sessions, entitlement-aware page reads, access logs, and JSON endpoints.

**Architecture:** Create a Django app named `document_reader`. It consumes `accounts.user_has_entitlement`, `catalog.Document`, `document_ingestion.DocumentVersion`, and `document_processing.DocumentPage`/`ExtractedText`, but no upstream app imports it. The API is plain Django JSON; no DRF, external storage adapter, signed URL, DRM, offline package, or search backend is introduced.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, pytest, pytest-django, SQLite local/test fallback, PostgreSQL production compatibility.

## Global Constraints

- Raw files and generated assets must remain private.
- Reader payloads must not include storage keys, public URLs, signed URLs, or download URLs.
- Reading is allowed only for published, non-private documents with a processed current version.
- `free` published documents require an authenticated user but no entitlement in this slice.
- `subscription`, `institution_only`, `sponsored`, and `restricted` documents require an active `read` entitlement.
- Restricted page reads must re-check entitlement on every request, not only at session start.
- Do not implement anonymous free reading, real signed URLs, DRM, offline packages, streaming, downloads, search APIs, analytics, billing, or audit logs in this slice.

---

## File Structure

```text
backend/
  document_reader/
    __init__.py
    admin.py
    apps.py
    exceptions.py
    models.py
    services.py
    urls.py
    views.py
    migrations/
      __init__.py
    tests/
      __init__.py
      test_admin_registration.py
      test_bootstrap.py
      test_page_reads.py
      test_reader_api.py
      test_reader_sessions.py
  config/
    settings.py
    urls.py
  pyproject.toml
  pytest.ini
```

---

### Task 1: App Scaffold

**Files:**
- Create: `backend/document_reader/__init__.py`
- Create: `backend/document_reader/apps.py`
- Create: `backend/document_reader/migrations/__init__.py`
- Create: `backend/document_reader/tests/__init__.py`
- Create: `backend/document_reader/tests/test_bootstrap.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/pytest.ini`

**Interfaces:**
- Produces installed Django app `document_reader`.

- [ ] Write a failing bootstrap test asserting `apps.is_installed("document_reader")`.
- [ ] Add `DocumentReaderConfig`.
- [ ] Add `"document_reader"` to `INSTALLED_APPS`.
- [ ] Add `document_reader/tests` to pytest testpaths.
- [ ] Run the bootstrap test.
- [ ] Commit with `feat: add document reader app scaffold`.

---

### Task 2: Reader Session Models

**Files:**
- Create: `backend/document_reader/models.py`
- Create: `backend/document_reader/tests/test_reader_sessions.py`
- Generate: `backend/document_reader/migrations/0001_initial.py`

**Interfaces:**
- Produces `ReaderSession`.
- Produces `PageAccessLog`.

- [ ] Write failing tests for storing session metadata, rejecting a version from another document, active-session expiry behavior, ending a session, and successful page access log storage.
- [ ] Implement `ReaderSession` with `session_key`, `user`, `document`, `version`, `status`, `started_at`, `expires_at`, `ended_at`, `last_seen_at`, `client_ip`, and `user_agent`.
- [ ] Implement `ReaderSession.is_active_at(at=None) -> bool` and `ReaderSession.end(at=None)`.
- [ ] Validate that `version.document_id == document_id` and active sessions have future `expires_at`.
- [ ] Implement `PageAccessLog` with `session`, `page`, `user`, `document`, `page_number`, `accessed_at`, `client_ip`, and `user_agent`.
- [ ] Generate and run migrations.
- [ ] Run task tests.
- [ ] Commit with `feat: add reader session records`.

---

### Task 3: Session Authorization Service

**Files:**
- Create: `backend/document_reader/exceptions.py`
- Create: `backend/document_reader/services.py`
- Modify: `backend/document_reader/tests/test_reader_sessions.py`

**Interfaces:**
- Produces `ReaderAccessDenied`.
- Produces `start_reader_session(*, user, document, client_ip="", user_agent="", at=None) -> ReaderSession`.
- Produces `end_reader_session(*, session, at=None) -> ReaderSession`.

- [ ] Write failing tests showing unpublished documents, private documents, and restricted documents without entitlement cannot start sessions.
- [ ] Write passing-target tests showing published free documents and restricted documents with active read entitlement can start sessions.
- [ ] Implement current processed version lookup from `DocumentVersion` with `is_current=True` and `status=processed`.
- [ ] Implement `document_requires_entitlement(document) -> bool`.
- [ ] Implement `user_can_read_document(user, document, at=None) -> bool`.
- [ ] Implement `start_reader_session()` with a 120-minute default TTL from `settings.READER_SESSION_TTL_MINUTES`.
- [ ] Implement `end_reader_session()`.
- [ ] Run task tests.
- [ ] Commit with `feat: authorize reader sessions`.

---

### Task 4: Reader Page Service

**Files:**
- Modify: `backend/document_reader/exceptions.py`
- Modify: `backend/document_reader/services.py`
- Create: `backend/document_reader/tests/test_page_reads.py`

**Interfaces:**
- Produces `ReaderSessionInactive`.
- Produces `ReaderPageUnavailable`.
- Produces `get_reader_page(*, session, page_number, at=None) -> dict`.

- [ ] Write failing tests showing expired sessions, ended sessions, expired entitlements, missing pages, unprocessed pages, and textless pages are rejected.
- [ ] Write a failing test showing successful page reads return a safe JSON-ready payload and create `PageAccessLog`.
- [ ] Implement page read validation and entitlement re-check for restricted documents.
- [ ] Ensure payload keys are exactly `session_key`, `document_id`, `version_id`, `page_number`, `page_count`, `language_code`, and `text`.
- [ ] Run task tests.
- [ ] Commit with `feat: serve authorized reader pages`.

---

### Task 5: Reader JSON API

**Files:**
- Create: `backend/document_reader/urls.py`
- Create: `backend/document_reader/views.py`
- Create: `backend/document_reader/tests/test_reader_api.py`
- Modify: `backend/config/urls.py`

**Interfaces:**
- Consumes `start_reader_session()`, `end_reader_session()`, and `get_reader_page()`.
- Produces Django endpoints under `/reader/`.

- [ ] Write failing API tests for unauthenticated start denial, session start, page read, denied restricted page read after entitlement expiry, and session end.
- [ ] Implement JSON views with status codes: `401` unauthenticated, `403` access/session denied, `404` unavailable page or document, `200` successful page read/session end, `201` session start.
- [ ] Add `document_reader.urls`.
- [ ] Include reader URLs in `config.urls`.
- [ ] Run API tests.
- [ ] Commit with `feat: add reader page json api`.

---

### Task 6: Admin And Full Verification

**Files:**
- Create: `backend/document_reader/admin.py`
- Create: `backend/document_reader/tests/test_admin_registration.py`

**Interfaces:**
- Produces admin registration for `ReaderSession` and `PageAccessLog`.

- [ ] Write a failing admin registration test.
- [ ] Register reader models in Django admin with useful filters, search fields, autocomplete fields, and readonly timestamps.
- [ ] Run `pytest document_reader/tests -q`.
- [ ] Run full backend verification: `pytest -q`, `python manage.py check`, `python manage.py makemigrations --check --dry-run`, and `python manage.py migrate`.
- [ ] Commit with `feat: expose document reader in admin`.

## Self-Review Checklist

- [ ] `document_reader` is installed and covered by pytest testpaths.
- [ ] Upstream apps do not import `document_reader`.
- [ ] Sessions cannot start for unpublished or private documents.
- [ ] Restricted documents require active read entitlement at session start and page read.
- [ ] Expired or ended sessions cannot read pages.
- [ ] Page reads require processed page records and extracted text.
- [ ] Reader payloads contain no storage key or URL fields.
- [ ] Successful page reads create access logs.
- [ ] JSON endpoints expose only the safe reader behavior in this slice.
- [ ] No signed URLs, DRM, offline packages, downloads, search APIs, analytics, billing, or audit implementation is added.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-27-bibliogabon-secure-reader.md`.

Recommended execution: sequential TDD in this session. The tasks share one app and should not be implemented by parallel agents against the same files.
