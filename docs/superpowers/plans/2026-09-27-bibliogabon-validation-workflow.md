# BiblioGABON Validation Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A moderator sees what is waiting, decides with a recorded reason, and the audit trail is visible. Withdrawal and archiving stop being unreachable states.

**Architecture:** Two new services in `operations/services.py`, eight endpoints in `/api/staff/v1/`, two screens under `/gestion/revues`, and the audit trail on the document detail screen. The domain — `PublicationReview`, `AuditLog`, `record_publication_decision` — already exists and is not rewritten.

**Tech Stack:** Django 5 / DRF, React 19 / TanStack, Vitest, pytest.

Slice 3 of 4 of `docs/superpowers/specs/2026-09-27-bibliogabon-back-office-design.md`.
Design: `docs/superpowers/specs/2026-09-27-bibliogabon-validation-workflow-design.md`.

## Global Constraints

- No staff response exposes a storage key, a signed URL or a source download link. The audit endpoint filters `metadata` through an allow-list, because audit metadata is written by many services and one of them could one day put a key in it.
- Every transition writes exactly one audit event naming the actor and the reason. A transition without one is a bug, not a missing nicety.
- A decision without a reason is refused: rejection and withdrawal both require one.
- A content admin who authored the document cannot decide on it. Separation of duties must not depend on role assignment alone.
- Withdrawal deletes nothing. Pages, version, index and rights stay; only readability changes.
- The public reader API and its tests are untouched.
- The six states of D014 are the only ones that exist. No new state is introduced.
- Use TDD: write the failing test, run it red for the expected reason, implement, run green, then commit.

---

### Task 1: Withdrawal And Archiving Services

**Files:**
- Modify: `backend/operations/services.py`
- Create: `backend/operations/tests/test_withdrawal.py`

**Interfaces:**
- Produces `withdraw_document(*, document, reason, actor=None, at=None)`.
- Produces `archive_document(*, document, reason, actor=None, at=None)`.

- [x] Write failing tests: withdrawing a published document sets `publication_status` and `withdrawn_at` and writes one audit event naming actor and reason; an empty reason is refused; withdrawing a draft is refused; archiving twice is refused.
- [x] Write a failing test that withdrawal keeps the version, its pages and its search index rows, and that the rights agreement is untouched — a withdrawal is not a rights revocation, and conflating them would make republication demand a fresh approval it does not need.
- [x] Write a failing test that a withdrawn document is unreadable through `document_is_reader_accessible` and through both reader surfaces.
- [x] Implement both services with `select_for_update`, shaped like `record_publication_decision`.
- [x] Run `python -m pytest operations catalog document_reader -q`.
- [x] Commit `feat: add withdrawal and archiving services`.

---

### Task 2: Review Queue Endpoints

**Files:**
- Create: `backend/api/staff/v1/reviews.py`, `backend/api/staff/v1/tests/test_reviews.py`
- Modify: `backend/api/staff/v1/urls.py`

**Interfaces:**
- Produces `GET/POST /api/staff/v1/reviews/`, `GET /reviews/<id>/`, `POST /reviews/<id>/assign/`, `POST /reviews/<id>/decision/`.

- [x] Write failing tests: a teacher-author is refused on every review endpoint; a content admin lists open reviews with what each document still misses for publication; opening a review on a document that is not submitted is refused; assigning sets the reviewer; a decision closes the review and moves the document.
- [x] Write a failing test that a content admin who authored the document is refused on its decision, and that the refusal is a typed error and not a 500.
- [x] Write a failing test that approving a document with unapproved rights is refused at the endpoint, with the blocking requirement named in the response.
- [x] Write a failing test that a rejection without a reason is refused with `field_errors` on the right field.
- [x] Implement on `StaffAPIView`, delegating to the existing services.
- [x] Run `python -m pytest api/staff/v1 -q`.
- [x] Commit `feat: expose the publication review queue`.

---

### Task 3: Withdrawal, Archiving And Audit Endpoints

**Files:**
- Create: `backend/api/staff/v1/lifecycle.py` — un module séparé plutôt qu'un ajout à `documents.py`, qui dépasse déjà la lecture confortable
- Create: `backend/api/staff/v1/tests/test_lifecycle.py`
- Modify: `backend/api/staff/v1/urls.py`

**Interfaces:**
- Produces `POST /documents/<id>/withdraw/`, `POST /documents/<id>/archive/`, `GET /documents/<id>/audit/`.

- [x] Write failing tests: a teacher-author withdraws their voluntary deposit but is refused on an institutional fund — the contract-bound categories, where a unilateral withdrawal would breach a contract; a content admin may do both.
- [x] Write failing tests: a withdrawal without a reason is refused; the audit endpoint lists events in order with actor, type, summary and date.
- [x] Write a failing test that the audit endpoint filters `metadata` through an allow-list, using a deliberately poisoned event containing a storage key. A privacy rule that depends on every future writer being careful is not a rule.
- [x] Implement, reusing `can_withdraw_document` rather than restating the category rule.
- [x] Run `python -m pytest api/staff/v1 -q`.
- [x] Commit `feat: expose withdrawal, archiving and the audit trail`.

---

### Task 4: Review Queue Screen

**Files:**
- Create: `frontend/src/routes/gestion/ReviewsPage.tsx`, `frontend/src/tests/staff-reviews.test.tsx`
- Modify: `frontend/src/api/staff.ts`, `frontend/src/api/types.ts`, `frontend/src/features/staff/hooks.ts`, `frontend/src/router.tsx`, `frontend/src/routes/gestion/GestionLayout.tsx`

**Interfaces:**
- Produces `/gestion/revues`.

- [x] Write failing tests: the queue renders each waiting document with what still blocks its publication, filters by state and by assignment, and renders loading, empty and refused states distinctly.
- [x] Write a failing test that a teacher-author sees the area refuse the queue rather than an empty list — hiding a link is a courtesy, and the screen must render a server refusal.
- [x] Write a failing test that no rendered row contains a storage key, a `.pdf` path or a `://`.
- [x] Implement the page and its hooks.
- [x] Run `npm run test`.
- [x] Commit `feat: add the review queue screen`.

---

### Task 5: Review Decision Screen

**Files:**
- Create: `frontend/src/routes/gestion/ReviewDetailPage.tsx`, `frontend/src/components/staff/DecisionForm.tsx`
- Modify: `frontend/src/tests/staff-reviews.test.tsx`, `frontend/src/router.tsx`

**Interfaces:**
- Produces `/gestion/revues/$reviewId`.

- [x] Write failing tests: the screen shows the rights status, the ingestion state and the page count; the approve control is disabled while `missing_for_publication` is non-empty **and the screen states which requirement blocks it**, rather than only greying a button.
- [x] Write failing tests: a rejection cannot be submitted without a reason; a server refusal lands on the right field; assigning oneself updates the screen.
- [x] Write a failing test that the screen offers no rights-approval control: D014 made `RightsAgreement.authorization_status` the single representation of that gate, and a second control here would be a second answer to one question.
- [x] Implement with `react-hook-form` and `applyApiErrors`, as slice 2 established.
- [x] Run `npm run test`.
- [x] Commit `feat: add the review decision screen`.

---

### Task 6: Withdrawal, Archiving And Audit Trail On The Document Screen

**Files:**
- Modify: `frontend/src/routes/gestion/DocumentDetailPage.tsx`
- Create: `frontend/src/components/staff/LifecycleActions.tsx`, `frontend/src/components/staff/AuditTrail.tsx`
- Modify: `frontend/src/tests/staff-deposit.test.tsx`

- [x] Write failing tests: the withdrawal action demands a reason and is absent for a state where it makes no sense; archiving likewise; the audit trail renders who, what, when and why in order.
- [x] Write a failing test that the audit trail renders an event whose metadata the server filtered, without assuming any field is present.
- [x] Write a failing test that no part of the trail contains a storage key, a `.pdf` path or a `://`.
- [x] Implement both components.
- [x] Run `npm run test`, `npm run lint`, `npm run build`.
- [x] Commit `feat: add lifecycle actions and the audit trail to the document screen`.

---

### Task 7: Verification And Documentation

**Files:**
- Modify: `CLAUDE.md`, `docs/product/02-phase-1-closure-register.md`

- [x] Extend `test_frontend_type_parity` to the review, audit and lifecycle payloads — the guard that stops a stub from lying must cover the new surface too.
- [x] Extend `test_frontend_enum_parity` to `PublicationReview.Status`.
- [x] Walk the flow against the running backend : 33 vérifications, toutes passées **après** correction. Le parcours a trouvé un trou qu'aucun test unitaire ne voyait : `SUBMITTABLE_STATES` n'acceptait que `draft`, donc un document rejeté restait bloqué à vie et un retrait n'était pas réversible, en contradiction avec la gouvernance.
- [x] Re-assert the bundle split: the reader entry chunk still contains no staff module.
- [x] Run the whole CI locally, both sides, with `REQUIRE_OCR=1`.
- [x] Document the workflow in `CLAUDE.md` and update the closure register.
- [x] Commit `docs: document the validation workflow`.

---

## Self-Review Checklist

- [x] A teacher-author is refused on the queue, the decision and the audit trail.
- [x] A content admin who authored the document is refused on its decision.
- [x] Approving with unapproved rights is refused at the endpoint, naming the requirement.
- [x] A rejection and a withdrawal both require a reason.
- [x] Withdrawal keeps pages, version, index and rights; only readability changes.
- [x] A withdrawn document is unreadable through both reader surfaces.
- [x] Republication goes through a new review and clears `withdrawn_at`.
- [x] Every transition writes exactly one audit event with actor and reason.
- [x] The audit endpoint's allow-list is tested with a poisoned event.
- [x] No screen or payload exposes a storage key, a `.pdf` path or a source URL.
- [x] The review screen offers no rights-approval control.
- [x] Reader routes, components and tests are unchanged.
- [x] Type and enum parity guards cover the new surface.

## Execution Handoff

Task 1 gates everything: the two missing services are what make four of the six states reachable. Tasks 2 and 3 can proceed in parallel once it lands. Task 5 carries the most product risk — an approve control that greys out without saying why is how a reviewer concludes the tool is broken.

After this slice, Phase 1's "workflow de validation" closes. Slice 4 — organizations, quotas and support — closes the rest of §8.2.
