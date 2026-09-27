# BiblioGABON Organizations, Quotas And Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An institution admin manages their members, quotas and usage report. A moderator triages support requests, document reports and withdrawal requests. Phase 1 closes.

**Architecture:** One model field, two services, twelve endpoints, three screens. The domain — memberships, quotas, entitlements, tickets, institution reports — exists and is reused unchanged.

Slice 4 of 4. Design: `docs/superpowers/specs/2026-09-27-bibliogabon-organizations-support-design.md`.

## Global Constraints

- Organization scope is an **argument** to the predicate, never a filter applied afterwards, and the refusal is asserted at the endpoint — predicate and endpoint can drift.
- No report, at any level, names who read what. Not deferred: excluded.
- Every membership and quota change goes through the audited services in `accounts.services` / `billing.services`. Writing the field directly loses the audit event.
- A withdrawal *request* withdraws nothing. It creates a ticket a moderator acts on, so that contract-bound categories keep their protection.
- No staff or public response exposes a storage key, a signed URL or a source download link.
- The reader API keeps its current shape; the two new public endpoints are additions, not changes.
- Use TDD: write the failing test, run it red for the expected reason, implement, run green, then commit.

---

### Task 1: Ticket Categories, Reports And Withdrawal Requests

**Files:**
- Modify: `backend/operations/models.py`, `backend/operations/services.py`
- Create: `backend/operations/migrations/00XX_supportticket_category.py`
- Create: `backend/operations/tests/test_reports_and_requests.py`

- [x] Write failing tests: reporting a published document creates a `document_report` ticket naming the reporter and the reason; an empty reason and an absent actor are both refused; an audit event is written.
- [x] Write failing tests: requesting withdrawal of a published document creates a `withdrawal_request` ticket and **changes nothing about the document**; requesting it on a draft is refused, because accepting would promise an act that cannot happen.
- [x] Write a failing test that resolving a withdrawal-request ticket leaves the document untouched — resolution is an answer, withdrawal is an act.
- [x] Add `SupportTicket.category` with a default of `support`, so existing rows keep their meaning.
- [x] Implement both services.
- [x] Run `python -m pytest operations -q`.
- [x] Commit `feat: distinguish reports and withdrawal requests from support`.

---

### Task 2: Public Report And Withdrawal-Request Endpoints

**Files:**
- Create: `backend/api/v1/reports.py`, `backend/api/v1/tests/test_reports.py`
- Modify: `backend/api/v1/urls.py`

- [x] Write failing tests: an authenticated reader reports a published document; an anonymous visitor is refused; reporting a draft returns **404, not 403** — answering "forbidden" would confirm the draft exists.
- [x] Write failing tests: an author requests withdrawal of their own published deposit; a reader who is not its author is refused; the response carries the ticket, never the document's storage details.
- [x] Write a failing test that the public OpenAPI schema documents both, and that the staff schema still does not.
- [x] Implement on the existing error envelope and permissions.
- [x] Run `python -m pytest api/v1 -q`.
- [x] Commit `feat: let readers report a document and authors request withdrawal`.

---

### Task 3: Staff Ticket Queue

**Files:**
- Create: `backend/api/staff/v1/tickets.py`, `backend/api/staff/v1/tests/test_tickets.py`
- Modify: `backend/api/staff/v1/urls.py`

- [ ] Write failing tests: a content admin lists tickets filtered by category and status; an organization admin sees only tickets attached to their own organization; a teacher is refused.
- [ ] Write failing tests: assigning records the assignee; resolving requires a summary and writes an audit event; resolving twice is refused.
- [ ] Write a failing test that resolving a withdrawal request does not touch the document, at the endpoint.
- [ ] Implement, reusing `resolve_support_ticket`.
- [ ] Run `python -m pytest api/staff/v1 -q`.
- [ ] Commit `feat: expose the support and report queue`.

---

### Task 4: Staff Organization Endpoints

**Files:**
- Create: `backend/api/staff/v1/organizations.py`, `backend/api/staff/v1/tests/test_organizations.py`
- Modify: `backend/api/staff/v1/urls.py`

- [ ] Write failing tests: an institution admin lists their organizations and only theirs; every endpoint refuses another organization, asserted at the endpoint and not only in the predicate.
- [ ] Write failing tests: members list carries verification status; adding, suspending and ending a membership each go through the audited service and write an event; suspending removes reading access immediately.
- [ ] Write failing tests: quotas list carries seat limits and contract references; the usage report returns aggregated metrics for a period.
- [ ] Write a failing test that scans the report payload for per-user fields — a future metric that adds one must fail the test, not leak.
- [ ] Implement, reusing the audited services unchanged.
- [ ] Run `python -m pytest api/staff/v1 -q`.
- [ ] Commit `feat: expose organization members, quotas and usage reports`.

---

### Task 5: Organization Screens

**Files:**
- Create: `frontend/src/routes/gestion/OrganizationsPage.tsx`, `.../OrganizationDetailPage.tsx`, `frontend/src/tests/staff-organizations.test.tsx`
- Modify: the staff client, types, hooks, router and layout

- [ ] Write failing tests: the list shows only administered organizations; the detail shows members with their verification status, quotas with contract references, and the usage report.
- [ ] Write a failing test that an unverified membership is visibly marked — an admin who does not see it will not understand why a member cannot read.
- [ ] Write failing tests: suspending a member asks for confirmation and reflects the result; a server refusal renders.
- [ ] Write a failing test that no rendered screen shows a per-user reading record.
- [ ] Implement.
- [ ] Run `npm run test`.
- [ ] Commit `feat: add the organization screens`.

---

### Task 6: Support Queue Screen

**Files:**
- Create: `frontend/src/routes/gestion/SupportPage.tsx`, `frontend/src/tests/staff-support.test.tsx`
- Modify: the staff client, types, hooks, router and layout

- [ ] Write failing tests: the queue filters by category and status; a withdrawal request links to its document and states plainly that resolving the ticket withdraws nothing.
- [ ] Write failing tests: resolving requires a summary; a server refusal lands on the field; loading, empty and refused states each render.
- [ ] Implement.
- [ ] Run `npm run test`, `npm run lint`, `npm run build`.
- [ ] Commit `feat: add the support and report queue screen`.

---

### Task 7: Phase 1 Closure

**Files:**
- Modify: `CLAUDE.md`, `docs/product/02-phase-1-closure-register.md`, `README.md`

- [ ] Extend both parity guards to the new payloads and to `SupportTicket.Category`.
- [ ] Walk the flow against the running backend: report a document, request a withdrawal, triage both, manage a membership, read a usage report, confirm a suspended member loses access.
- [ ] Re-assert the bundle split.
- [ ] Run the whole CI locally, both sides, with `REQUIRE_OCR=1`.
- [ ] Audit Phase 1 line by line against the plan directeur and record, honestly, what is done and what is not.
- [ ] Commit `docs: close Phase 1`.

---

## Self-Review Checklist

- [ ] An institution admin is refused on another organization at every endpoint.
- [ ] No payload or screen names who read what.
- [ ] A withdrawal request withdraws nothing, and the screen says so.
- [ ] Reporting a draft returns 404, not 403.
- [ ] Every membership and quota change is audited.
- [ ] A suspended membership removes reading access immediately.
- [ ] The report payload is scanned for per-user fields.
- [ ] Parity guards cover the new surface.
- [ ] Reader routes, components and tests are unchanged.

## Execution Handoff

Task 1 gates tasks 2 and 3. Task 4 is independent. The product risk sits in task 4: an organization endpoint that trusts a post-hoc filter instead of the predicate would expose one institution's members to another, and that is the kind of defect that survives a passing test suite.

After this slice, Phase 1 closes. Task 7's honest audit matters more than the code: a line marked complete on the strength of a half-measure is what produced the back-office gap in the first place.
