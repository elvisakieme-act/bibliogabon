# BiblioGABON Role Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the seven actors of the product document into permissions the code applies, so the deposit slice can say who may deposit and who may validate.

**Architecture:** One set of plain predicate functions in `accounts/permissions.py` as the single source of truth, wrapped by DRF permission classes for the API and by permission methods on the admin classes. Organization scope is an argument to the predicate, never a filter applied afterwards.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, Django REST Framework, pytest, pytest-django.

## Global Constraints

- Roles govern actions; entitlements govern content access. Neither substitutes for the other, and the existing reader tests must pass untouched.
- An institution admin acts on their own organization and nowhere else.
- Administrative authority follows the same membership rules as reading: a suspended, ended or unverified membership grants nothing.
- Every state-changing action reachable through a role records an `operations.AuditLog` event naming the actor.
- Every boundary in the spec gets a test proving the wrong actor is refused.
- `is_staff` keeps deciding whether the admin site opens; the predicates decide what is usable inside it.
- Do not build the upload endpoint, the deposit screen, an institution dashboard, invitations, or any reader hardening.
- Use TDD: write the failing test, run it red for the expected reason, implement, run green, then commit.

---

## File Structure

```text
backend/
  accounts/
    models.py                 # AccountType.CONTENT_ADMIN
    permissions.py            # predicates: the single source of truth
    admin.py
    migrations/
    tests/
      test_permissions.py
      test_permission_scope.py
  api/
    v1/
      permissions.py          # DRF wrappers
      tests/test_permissions_api.py
  catalog/admin.py
  operations/admin.py
  billing/admin.py
  document_ingestion/management/commands/seed_demo.py
```

---

### Task 1: Account Type For The Content Admin

**Files:**
- Modify: `backend/accounts/models.py`, `backend/accounts/admin.py`
- Create: migration
- Modify: `backend/accounts/tests/test_user_model.py`

**Interfaces:**
- Produces `AccountType.CONTENT_ADMIN`.

- [x] Write a failing test: a content-admin account can be created, is distinct from `platform_staff`, and `create_superuser` still yields `platform_staff` with `is_superuser`.
- [x] Add the choice and generate the migration. No existing row changes meaning: current `platform_staff` accounts stay super admins, which is the safe direction.
- [x] Check the admin list filter still reads clearly with five values.
- [x] Run `pytest accounts/tests -q`.
- [x] Commit `feat: add a content admin account type`.

---

### Task 2: Permission Predicates

**Files:**
- Create: `backend/accounts/permissions.py`, `backend/accounts/tests/test_permissions.py`

**Interfaces:**
- Produces `is_platform_staff`, `is_content_admin`, `administers_organization`, `administered_organization_ids`, `can_submit_document`, `can_review_publication`, `can_withdraw_document`, `can_manage_organization_members`, `can_view_organization_reports`, `can_manage_billing`.

- [x] Write a failing table-driven test covering all seven actors against every predicate, including the anonymous visitor and the plain student, which must answer False everywhere.
- [x] Write failing tests for `can_withdraw_document`: a teacher may withdraw their own voluntary deposit; the same teacher may not withdraw an institutional-fund document; a content admin may withdraw either.
- [x] Implement the predicates as pure reads with no HTTP and no DRF import.
- [x] Keep the contract-bound categories as string literals: `catalog` depends on `accounts`, so importing
      `Document` here would invert the dependency. A test locks the literals against `Document.Category`.
- [x] Reuse `active_organization_ids_for_user` for organization scope, so membership status and identity verification govern administrative authority exactly as they govern reading.
- [x] Run `pytest accounts/tests/test_permissions.py -q`.
- [x] Commit `feat: add role permission predicates`.

---

### Task 3: Organization Scope

**Files:**
- Create: `backend/accounts/tests/test_permission_scope.py`

**Interfaces:**
- Hardens the organization-scoped predicates from Task 2.

- [x] Write failing tests: an admin of organization A is refused on organization B; an admin of two organizations is accepted on both; a suspended membership, an ended membership, and an unverified identity in a verification-required organization each remove administrative authority while the account stays usable as a reader.
- [x] Nothing to fix: all eight passed first run, because Task 2 reused `active_organization_ids_for_user`
      rather than reimplementing membership rules. The tests stand as a regression lock on that reuse.
- [x] Run `pytest accounts/tests -q`.
- [x] Commit `test: cover organization scope of administrative authority`.

---

### Task 4: DRF Permission Classes

**Files:**
- Create: `backend/api/v1/permissions.py`, `backend/api/v1/tests/test_permissions_api.py`

**Interfaces:**
- Produces `IsContentAdmin`, `IsTeacherOrContentAdmin`, `AdministersOrganization`.

- [ ] Write failing tests exercising the classes through a throwaway view: each refuses the wrong actor with HTTP 403 and the standard envelope code `permission_denied`, and an anonymous caller gets 401 rather than 403.
- [ ] Implement the classes as thin wrappers over the predicates, with no logic of their own.
- [ ] Note in the module docstring that the current V1 surface is reader-facing and has no management endpoint yet: these classes exist for the deposit slice, which is the first real consumer. Wiring them to endpoints that do not need them would be noise.
- [ ] Run `pytest api/v1/tests -q`.
- [ ] Commit `feat: add API permission classes for roles`.

---

### Task 5: Admin Authority

**Files:**
- Modify: `backend/catalog/admin.py`, `backend/operations/admin.py`, `backend/billing/admin.py`, `backend/accounts/admin.py`
- Create: `backend/operations/tests/test_admin_authority.py`

**Interfaces:**
- Derives admin add/change/delete permissions from the predicates.

- [ ] Write failing tests: a content admin may act on publication reviews and catalog records but is refused on billing models and on platform-role fields; a super admin may act on everything; an institution admin without `is_staff` cannot open the admin at all; `AuditLog` stays append-only for every actor.
- [ ] Implement `has_add_permission`, `has_change_permission` and `has_delete_permission` from the predicates on the affected admin classes.
- [ ] Leave the reader, ingestion and processing admins as staff-only inspection surfaces; they expose no role-bearing action.
- [ ] Run `pytest operations/tests billing/tests catalog/tests accounts/tests -q`.
- [ ] Commit `feat: derive admin authority from roles`.

---

### Task 6: Audit The Role-Bearing Actions

**Files:**
- Modify: `backend/accounts/services.py`, `backend/operations/services.py` if a helper is missing
- Create: `backend/accounts/tests/test_membership_audit.py`

**Interfaces:**
- Produces audited membership changes.

- [ ] Write failing tests: adding, suspending and removing a member records an `AuditLog` event naming the actor, the organization and the member; an entitlement granted under a role records one too.
- [ ] Implement the service functions that perform those changes, calling `record_audit_event`. Direct model saves stay possible but are not the path the admin uses.
- [ ] Run `pytest accounts/tests operations/tests -q`.
- [ ] Commit `feat: audit membership and entitlement changes`.

---

### Task 7: Demo Data, Documentation And Verification

**Files:**
- Modify: `backend/document_ingestion/management/commands/seed_demo.py`, `CLAUDE.md`, `AGENTS.md`, `docs/product/00-decision-register.md`

- [ ] Add a content-admin account to `seed_demo`, so the deposit slice has a reviewer to work with, and print it with the other demo accounts.
- [ ] Document the actor-to-storage mapping in `CLAUDE.md`: roles govern actions, entitlements govern content, and organization scope comes from an active verified membership.
- [ ] Record in the decision register that Content Admin became its own account type, and that Sponsor Partner is an organization admin of a sponsor organization rather than a fifth type.
- [ ] Run full verification: `pytest -q`, `manage.py check`, `manage.py makemigrations --check --dry-run`, `git diff --check`.
- [ ] Commit `docs: document the role matrix`.

---

## Self-Review Checklist

- [ ] Every predicate has a test per actor, including the two that must answer False everywhere.
- [ ] Organization scope is an argument, never a post-hoc filter.
- [ ] Suspended, ended and unverified memberships grant no administrative authority.
- [ ] No role grants reading access; the existing reader and entitlement tests pass untouched.
- [ ] A teacher cannot approve their own submission.
- [ ] An institution admin cannot publish, withdraw, change rights, alter pricing, modify platform roles, or see private processing states.
- [ ] A content admin cannot manage billing or platform configuration.
- [ ] Role-bearing state changes record an audit event naming the actor.
- [ ] `AuditLog` remains append-only.
- [ ] No upload endpoint, deposit screen, dashboard, invitation flow or reader hardening was added.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-27-bibliogabon-role-enforcement.md`.

Recommended execution: sequential TDD. Tasks 2 and 3 share `permissions.py`, and Task 5 touches four admin modules that Task 2 must exist for. Task 1 is independent and can go first in either order.

This slice closes the "rôles" half of Phase 1's "authentification et rôles". The deposit slice closes the other gap, and Phase 1 with it.
