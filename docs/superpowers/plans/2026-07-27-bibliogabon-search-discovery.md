# BiblioGABON Search Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a database-backed public search foundation for discoverable BiblioGABON documents without exposing reader content or storage data.

**Architecture:** Create a Django app named `search_discovery` with one denormalized index model, focused indexing services, a deterministic search service, and a public JSON endpoint. The app consumes catalog, ingestion, and processing data; upstream apps do not import it.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, pytest, pytest-django, SQLite local/test fallback, PostgreSQL production compatibility.

## Global Constraints

- A document is discoverable only when `publication_status` is `published` and `access_model` is not `private`.
- Public search may expose metadata for restricted documents, but never page text snippets.
- Search payloads must not include storage keys, public URLs, signed URLs, download URLs, reader session keys, or raw page text.
- Extracted page text is internal index material only.
- Use plain Django views and `JsonResponse`; do not add DRF or an external search engine.
- Keep ranking deterministic and database-portable.

---

## File Structure

```text
backend/
  search_discovery/
    __init__.py
    admin.py
    apps.py
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
      test_indexing.py
      test_search_api.py
      test_search_service.py
  config/
    settings.py
    urls.py
  pyproject.toml
  pytest.ini
```

---

### Task 1: App Scaffold

**Files:**
- Create: `backend/search_discovery/__init__.py`
- Create: `backend/search_discovery/apps.py`
- Create: `backend/search_discovery/migrations/__init__.py`
- Create: `backend/search_discovery/tests/__init__.py`
- Create: `backend/search_discovery/tests/test_bootstrap.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/pytest.ini`

**Interfaces:**
- Produces installed Django app `search_discovery`.

- [ ] Write a failing test:

```python
from django.apps import apps


def test_search_discovery_app_is_installed():
    assert apps.is_installed("search_discovery")
```

- [ ] Run `pytest search_discovery/tests/test_bootstrap.py -q`; expected failure is that the test path or app does not exist yet.
- [ ] Add `SearchDiscoveryConfig` with `name = "search_discovery"`.
- [ ] Add `"search_discovery"` to `INSTALLED_APPS`.
- [ ] Add `search_discovery/tests` to both pytest testpath declarations.
- [ ] Run `pytest search_discovery/tests/test_bootstrap.py -q`; expected pass.
- [ ] Commit with `feat: add search discovery app scaffold`.

---

### Task 2: Document Search Index Model

**Files:**
- Create: `backend/search_discovery/models.py`
- Create: `backend/search_discovery/tests/test_indexing.py`
- Generate: `backend/search_discovery/migrations/0001_initial.py`

**Interfaces:**
- Produces `DocumentSearchIndex`.

- [ ] Write failing tests proving an index row stores safe denormalized metadata and rejects blank titles:

```python
index = DocumentSearchIndex.objects.create(
    document=document,
    title="Pedagogie universitaire",
    slug="pedagogie-universitaire",
    abstract="Analyse des pratiques.",
    language_code="fr",
    publication_year=2026,
    access_model=Document.AccessModel.FREE,
    domain_name="Education",
    domain_slug="education",
    author_names="Aline NZE\nBrice ONDO",
    metadata_text="Pedagogie universitaire Analyse des pratiques.",
    page_text="Texte interne non expose.",
    indexed_page_count=1,
)

assert index.title == "Pedagogie universitaire"
assert index.author_names.splitlines() == ["Aline NZE", "Brice ONDO"]
```

- [ ] Run `pytest search_discovery/tests/test_indexing.py -q`; expected failure is `ModuleNotFoundError` or missing `DocumentSearchIndex`.
- [ ] Implement `DocumentSearchIndex` as a one-to-one row for `catalog.Document`.
- [ ] Add indexes for `domain_slug`, `language_code`, `access_model`, and `publication_year`.
- [ ] Implement `save()` with `full_clean()` and validation that `title` is not blank.
- [ ] Run `python manage.py makemigrations search_discovery`.
- [ ] Run `pytest search_discovery/tests/test_indexing.py -q`; expected pass.
- [ ] Commit with `feat: add document search index model`.

---

### Task 3: Indexing Services

**Files:**
- Create: `backend/search_discovery/services.py`
- Modify: `backend/search_discovery/tests/test_indexing.py`

**Interfaces:**
- Produces `document_is_discoverable(document) -> bool`.
- Produces `rebuild_document_search_index(document) -> DocumentSearchIndex | None`.
- Produces `rebuild_all_document_search_indexes() -> int`.

- [ ] Write failing tests for:
  - published non-private documents creating index rows;
  - private, draft, withdrawn, and suspended documents deleting index rows;
  - ordered authors appearing in `author_names`;
  - page text coming only from processed pages on the current processed version.
- [ ] Run targeted tests; expected failure is missing services.
- [ ] Implement `document_is_discoverable()` from the product rule.
- [ ] Implement `rebuild_document_search_index()` with a transaction, metadata copy, ordered author aggregation, and current processed page-text aggregation.
- [ ] Implement `rebuild_all_document_search_indexes()` over all catalog documents.
- [ ] Run `pytest search_discovery/tests/test_indexing.py -q`; expected pass.
- [ ] Commit with `feat: rebuild document search indexes`.

---

### Task 4: Search Service

**Files:**
- Modify: `backend/search_discovery/services.py`
- Create: `backend/search_discovery/tests/test_search_service.py`

**Interfaces:**
- Produces `search_documents(query="", domain_slug="", language_code="", access_model="", publication_year=None, limit=20) -> list[dict]`.

- [ ] Write failing tests for:
  - title matches outranking body-only matches;
  - author, domain, abstract, and body text matching;
  - filters for `domain_slug`, `language_code`, `access_model`, and `publication_year`;
  - empty queries returning indexed records sorted by title;
  - result dictionaries excluding `page_text`, `storage_key`, `url`, and `session_key`.
- [ ] Run targeted tests; expected failure is missing `search_documents`.
- [ ] Implement portable filtering with Django ORM and deterministic Python scoring.
- [ ] Return safe dictionaries with `academic_domain`, `authors`, `indexed_page_count`, `score`, and `text_match`.
- [ ] Enforce `limit` between 1 and 50 inside the service.
- [ ] Run `pytest search_discovery/tests/test_search_service.py -q`; expected pass.
- [ ] Commit with `feat: search indexed documents`.

---

### Task 5: Public Search API

**Files:**
- Create: `backend/search_discovery/urls.py`
- Create: `backend/search_discovery/views.py`
- Create: `backend/search_discovery/tests/test_search_api.py`
- Modify: `backend/config/urls.py`

**Interfaces:**
- Produces `GET /search/documents/`.

- [ ] Write failing tests for:
  - `GET /search/documents/?q=pedagogie` returning `{"count": 1, "results": [...]}`;
  - filters mapping `domain`, `language`, `access`, `year`, and `limit` to the service;
  - invalid `year` and `limit` returning JSON 400 errors;
  - payload safety excluding raw page text and storage fields.
- [ ] Run targeted tests; expected failure is 404 for `/search/documents/`.
- [ ] Implement `search_documents_view()` with `@require_GET`.
- [ ] Parse query parameters and return `{"error": "invalid_year"}` or `{"error": "invalid_limit"}` with HTTP 400 when parsing fails.
- [ ] Include `search_discovery.urls` at `/search/`.
- [ ] Run `pytest search_discovery/tests/test_search_api.py -q`; expected pass.
- [ ] Commit with `feat: expose public document search api`.

---

### Task 6: Admin And Verification

**Files:**
- Create: `backend/search_discovery/admin.py`
- Create: `backend/search_discovery/tests/test_admin_registration.py`

**Interfaces:**
- Registers `DocumentSearchIndex` in Django admin.

- [ ] Write failing test:

```python
from django.contrib import admin

from search_discovery.models import DocumentSearchIndex


def test_search_discovery_models_are_registered_in_admin():
    assert DocumentSearchIndex in admin.site._registry
```

- [ ] Run `pytest search_discovery/tests/test_admin_registration.py -q`; expected failure is unregistered model.
- [ ] Register `DocumentSearchIndexAdmin` with list display for document, language, access model, domain slug, indexed page count, and indexed date.
- [ ] Run the admin test; expected pass.
- [ ] Run full verification:

```bash
pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
git diff --check
```

- [ ] Commit with `test: cover search discovery admin`.

---

### Task 7: Review And Finish

**Files:**
- Modify only files flagged by review findings.

**Interfaces:**
- Produces a reviewed, verified feature branch ready for merge choice.

- [ ] Request code review focused on search safety, indexing correctness, API behavior, and migration quality.
- [ ] For each concrete finding, reproduce or reason from code, write or update a failing test when behavior changes, implement the minimal fix, and rerun targeted tests.
- [ ] Rerun full verification:

```bash
pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
git diff --check
```

- [ ] Commit review fixes if any.
- [ ] Present finishing options for the branch.
