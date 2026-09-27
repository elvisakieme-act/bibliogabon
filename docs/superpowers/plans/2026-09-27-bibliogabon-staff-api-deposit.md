# BiblioGABON Staff API And Document Deposit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the product a document deposit path that is not a shell command — a role-guarded staff API through which a teacher submits a document, attaches its authors and rights, uploads its file, and follows ingestion.

**Architecture:** A separate namespace `/api/staff/v1/` with its own OpenAPI schema, reusing the existing services unchanged: `ingest_document_file` for deposit, the role predicates for authorisation, the V1 error envelope and pagination for shape. The staff API owns serialization, validation and HTTP; it owns no business rule.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, Django REST Framework, drf-spectacular, pytest, pytest-django.

Slice 1 of 4 of `docs/superpowers/specs/2026-09-27-bibliogabon-back-office-design.md`.

## Global Constraints

- Authority comes from the role predicates in `accounts/permissions.py`. No endpoint invents its own rule.
- A teacher sees and edits the documents they authored; a content admin sees everything. Scope is enforced on the queryset, not only on the detail view.
- No staff response exposes a storage key, a signed URL or a download link to the source file. The upload goes in; nothing comes back out.
- Every state change records an audit event naming the actor.
- The public `/api/v1/` contract does not move. Its tests must pass untouched, and its schema must not gain a staff endpoint.
- Slice 1 uses only `draft` and `submitted`. The ten-versus-five publication-state question belongs to slice 3 and must not be pre-empted here.
- Do not build screens, the review workflow, organization management, notifications, bulk import or EPUB.
- Use TDD: write the failing test, run it red for the expected reason, implement, run green, then commit.

---

## File Structure

```text
backend/
  api/
    staff/
      __init__.py
      apps.py                  # if a distinct app label is needed
      v1/
        __init__.py
        urls.py
        views.py               # index
        documents.py           # list, create, detail, patch, submit
        contributors.py        # authors and rights
        deposit.py             # multipart upload, ingestion status
        serializers.py
        scoping.py             # the queryset a given actor may see
        tests/
          test_staff_api_foundation.py
          test_document_endpoints.py
          test_scoping.py
          test_contributors.py
          test_deposit.py
  config/
    settings.py                # upload limits
    urls.py                    # /api/staff/v1/ and its schema
```

---

### Task 1: Namespace, Schema And Authorisation Floor

**Files:**
- Create: `backend/api/staff/__init__.py`, `.../v1/__init__.py`, `.../v1/urls.py`, `.../v1/views.py`, `.../v1/tests/test_staff_api_foundation.py`
- Modify: `backend/config/urls.py`, `backend/config/settings.py`, `backend/pytest.ini`, `backend/pyproject.toml`

**Interfaces:**
- Produces `GET /api/staff/v1/` and `GET /api/staff/v1/schema/`.
- Produces a base view that refuses anyone without a staff role.

- [x] Write failing tests: the index refuses an anonymous caller with 401 and a student with 403 and the standard envelope; a content admin gets 200; the schema endpoint serves a document listing staff paths.
- [x] Write a failing test asserting the **public** schema at `/api/v1/schema/` contains no path starting with `/api/staff/`. Two audiences, two contracts — a staff endpoint leaking into the public schema is the failure this slice must not commit.
- [x] Route the namespace and give **each** schema its own URL perimeter (`config/schema_public.py`,
      `config/schema_staff.py`). Scoping only the staff schema would have left the public one generating from
      the root urlconf, which now contains the staff paths — the leak would have happened by default.
- [x] Add `has_back_office_access` and a `StaffAPIView` base class: the project default permission is
      `AllowAny`, so inheriting `APIView` directly would make a forgotten permission silently public.
- [x] Add `api/staff/v1/tests` to both pytest testpath declarations, or the tests silently never run.
- [x] Run `pytest api/staff -q` and `pytest api/v1/tests -q`.
- [x] Commit `feat: add the staff API namespace`.

---

### Task 2: What Each Actor May See

**Files:**
- Create: `backend/api/staff/v1/scoping.py`, `.../tests/test_scoping.py`

**Interfaces:**
- Produces `documents_visible_to(user) -> QuerySet`.

- [x] Write failing tests: a content admin sees documents in every state, including `draft` and `private`; a teacher sees only documents they authored, in any state; a teacher sees nothing authored by someone else; a student and an anonymous caller see nothing.
- [x] Write a failing test proving the reader-facing catalog is unaffected: the public list still excludes unpublished and private documents for the same content admin. The staff surface widens visibility for staff endpoints only.
- [x] Implement the queryset, deriving authorship through `Author.linked_user` as the predicates do, with
      `distinct()`: an author attached twice (author then co-author) would otherwise duplicate the row
      through the join.
- [x] Expose `is_teacher_author` rather than reading the private `_account_type` from another module.
- [x] Run `pytest api/staff -q`.
- [x] Commit `feat: scope staff document visibility by role`.

---

### Task 3: Document Read And Write

**Files:**
- Create: `backend/api/staff/v1/documents.py`, `.../v1/serializers.py`, `.../tests/test_document_endpoints.py`
- Modify: `.../v1/urls.py`

**Interfaces:**
- Produces `GET/POST /api/staff/v1/documents/`, `GET/PATCH /api/staff/v1/documents/{id}/`, `POST /api/staff/v1/documents/{id}/submit/`.

- [x] Write failing tests: a teacher creates a document and it lands in `draft` with them as author; the payload exposes publication state, rights presence and ingestion state, and no storage key; a teacher cannot patch a document they did not author; a content admin can; filters on state, domain and type work; the list is paginated with the standard envelope.
- [x] Write failing tests for `submit`: `draft → submitted` records an audit event naming the actor; submitting twice is idempotent; submitting a document with no author or no rights agreement is refused with a typed error naming what is missing.
- [x] Implement the views on the scoped queryset, reusing `StandardResultsSetPagination` and `error_response`.
- [x] Refactor `document_is_publishable` onto `missing_publication_requirements`, which returns *which*
      requirements are unmet. A boolean could not tell a depositor what is blocking, and restating the list
      in the API would have guaranteed divergence. The 18 catalog tests pass unchanged.
- [x] A document out of scope returns 404, not 403: answering "forbidden" would confirm it exists, and for
      someone else's draft that alone is a leak.
- [x] `publication_status` is absent from the write serializer. Leaving it writable would let a PATCH bypass
      the audited transitions entirely.
- [x] Run `pytest api/staff -q`.
- [x] Commit `feat: add staff document endpoints`.

---

### Task 4: Authors And Rights

**Files:**
- Create: `backend/api/staff/v1/contributors.py`, `.../tests/test_contributors.py`
- Modify: `.../v1/urls.py`, `.../v1/serializers.py`

**Interfaces:**
- Produces `POST/DELETE /api/staff/v1/documents/{id}/authors/...` and `PUT /api/staff/v1/documents/{id}/rights/`.

- [x] Write failing tests: attaching an author sets its position and role; attaching the same author twice is refused rather than duplicated; detaching leaves the ordering contiguous; the rights agreement can be created then replaced, and an invalid authorisation status is refused.
- [x] Separation of duties, decided with the product owner: the depositor declares, the moderator verifies.
      Structural, not conventional — the declaration serializer simply does not expose the decision fields,
      and the decision endpoint is closed to non-moderators. A depositor who sends `approved` is capped to
      `pending_review`.
- [x] **Fixed a defect introduced in Task 3.** The submit gate required a *publishable* document, so it
      required an *approved* rights agreement — but approval is the reviewer's act and comes after
      submission. No teacher could ever submit. `missing_deposit_requirements` (declaration complete) and
      `missing_publication_requirements` (declaration approved) are now two gates. The Task 3 test passed
      only because its fixture pre-approved the agreement: the setup was hiding the flaw.
- [x] Student work requires an explicit consent reference, per the governance document.
- [x] Implement, reusing the catalog models and validation.
- [x] Run `pytest api/staff catalog/tests -q`.
- [x] Commit `feat: manage document authors and rights from the staff API`.

---

### Task 5: Source Upload

**Files:**
- Create: `backend/api/staff/v1/deposit.py`, `.../tests/test_deposit.py`
- Modify: `backend/config/settings.py`, `backend/.env.example`

**Interfaces:**
- Produces `POST /api/staff/v1/documents/{id}/source/` accepting `multipart/form-data`.
- Produces settings `DOCUMENT_UPLOAD_MAX_BYTES` and `DOCUMENT_UPLOAD_ACCEPTED_MIME_TYPES`.

- [ ] Write failing tests: uploading the three-page fixture stores it privately and returns the version and its state, never a storage key; the response body contains no `storage`, no `.pdf` path and no URL; a file above the limit is refused with a typed error; an unaccepted MIME type is refused; a second upload to a populated version returns the `VersionAlreadyIngested` conflict as HTTP 409 with a code, and `?replace=true` succeeds.
- [ ] Write a failing test proving the file is not read into memory: upload a file larger than `FILE_UPLOAD_MAX_MEMORY_SIZE` and assert Django handed a `TemporaryUploadedFile` to the service. Both uploaded-file classes are seekable, which `ingest_document_file` requires.
- [ ] Implement the view with `parser_classes = [MultiPartParser]`. This is a deliberate exception to the JSON-only rule of the public contract, and the docstring must say so: a file cannot travel as JSON without base64 inflating it by a third.
- [ ] Enforce the limits before touching storage, so a refused upload writes nothing.
- [ ] Run `pytest api/staff document_ingestion/tests -q`.
- [ ] Commit `feat: accept document uploads through the staff API`.

---

### Task 6: Ingestion Status

**Files:**
- Modify: `backend/api/staff/v1/deposit.py`, `.../tests/test_deposit.py`

**Interfaces:**
- Produces `GET /api/staff/v1/documents/{id}/ingestion/`.

- [ ] Write failing tests: the endpoint reports version state, page count, job state, retry count and error code; a failed job surfaces its reason; a document with no version reports that plainly rather than 404; the payload exposes no storage key.
- [ ] Write a failing test for the asynchronous case: with tasks queued rather than eager, the endpoint reports the job as queued or running instead of pretending it is done. This is what the back-office screen will poll.
- [ ] Implement, reading the current version and its job.
- [ ] Run `pytest api/staff -q`.
- [ ] Commit `feat: report ingestion status to the staff API`.

---

### Task 7: OpenAPI, Documentation And Verification

**Files:**
- Modify: every staff view, `CLAUDE.md`, `AGENTS.md`, `README.md`
- Create: `backend/api/staff/v1/tests/test_openapi_staff.py`

- [ ] Write a failing test asserting every staff path carries a summary, a description, request and response schemas and its authentication requirement — the same guard `api/v1/tests/test_openapi_schema.py` provides for the public API.
- [ ] Re-assert, at the end, that the public schema still contains no staff path.
- [ ] Annotate the views with `@extend_schema`.
- [ ] Document the staff API in `CLAUDE.md` — separate namespace, separate schema, role-guarded, multipart exception — and the deposit flow in `README.md`.
- [ ] Run full verification: `pytest -q`, `manage.py check`, `manage.py makemigrations --check --dry-run`, `git diff --check`.
- [ ] Commit `docs: document the staff API`.

---

## Self-Review Checklist

- [ ] Every staff endpoint refuses the wrong role with the standard envelope; anonymous gets 401, wrong role 403.
- [ ] A teacher sees and edits only their own documents; a content admin sees every state.
- [ ] No staff response contains a storage key, a URL or a source download link.
- [ ] The public schema contains no staff path, and the public API tests are untouched.
- [ ] An upload over the size limit or of an unaccepted type is refused before anything is written.
- [ ] A large upload reaches the service as a temporary file, not as bytes in memory.
- [ ] Re-uploading to a populated version returns 409, and `replace=true` works.
- [ ] `draft → submitted` is audited, idempotent, and refused when authors or rights are missing.
- [ ] Only `draft` and `submitted` are used; the remaining publication states are untouched.
- [ ] No screen, review workflow, organization management, notification, bulk import or EPUB was added.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-27-bibliogabon-staff-api-deposit.md`.

Recommended execution: sequential TDD. Task 2 gates tasks 3 to 6, which all read through the scoped queryset. Task 5 is the only one introducing a new mechanism and deserves the closest review.

This slice closes the "dépôt documentaire" half of Phase 1's third line at the API level. Slice 2 puts a screen on it.
