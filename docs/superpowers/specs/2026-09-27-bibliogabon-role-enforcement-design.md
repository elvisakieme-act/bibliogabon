# BiblioGABON Role Enforcement Design

## Purpose

This slice turns the seven actors of `docs/product/01-users-roles-organizations.md` into permissions the code actually applies. It is the first of the two slices that close Phase 1 of the launch roadmap; the second is the document deposit path, which cannot be scoped without it.

It does not add an upload endpoint, a deposit screen, an institution dashboard, or any reader hardening. Those belong to the deposit slice and to Phase 2.

## Why This Slice Exists

The roadmap's Phase 1 asks for "authentification **et rôles**". Authentication is done. Roles are declared and never applied.

Verified on 2026-09-27:

- `User.AccountType` holds `individual`, `teacher_author`, `organization_admin`, `platform_staff`. It is written at registration, displayed in the admin and returned by `/api/v1/me/`. **No code branches on it.**
- `OrganizationMembership.Role` holds `member` and `admin`. **No code branches on it either.**
- The only permission class used anywhere in the API is DRF's `IsAuthenticated`, on four personal-library views and two auth views. There is no custom permission class in the codebase.
- Management authority is `is_staff`, a boolean that opens the whole Django Admin.

So an Institution Admin has no capability at all, a Teacher/Author has no capability at all, and the only way to grant anyone any management power today is to make them a full platform administrator — exactly the delegation the product document forbids.

Content access is a separate axis and is already sound: `accounts.Entitlement` gates restricted reading and is enforced on every page request. This slice does not touch it. The product rule is that identity, role and entitlement stay three distinct things; today only two of the three exist in code.

## Product Rules

Authority over *content access* comes from entitlements. Authority over *actions* comes from roles. A role never grants reading access, and an entitlement never grants a management action.

An institution admin acts on their own organization and nothing else. Scope is not a filter applied late in a view; it is part of the permission question, so a permission predicate that concerns an organization always takes the organization as an argument.

Platform staff may override access only through auditable actions. Any role-bearing action that changes publication, membership or entitlement state records an `operations.AuditLog` event.

Denial is a tested behaviour, not an accident. Every predicate has at least one test proving the wrong actor is refused, consistent with the repository's testing convention for reader access and billing.

## Actor Mapping

Seven actors, three storage axes. The mapping below is the part that needs deciding, because the current model cannot express two of the actors.

| Actor | Expressed as |
|---|---|
| Visitor | no account |
| Student | `AccountType.INDIVIDUAL` |
| Teacher/Author | `AccountType.TEACHER_AUTHOR` |
| Institution Admin | `AccountType.ORGANIZATION_ADMIN` + an active `OrganizationMembership` with `Role.ADMIN` naming the organization |
| Sponsor Partner | the same, on an organization whose `organization_type` is `sponsor` |
| BiblioGABON Content Admin | **new** `AccountType.CONTENT_ADMIN` |
| BiblioGABON Super Admin | `AccountType.PLATFORM_STAFF` with `is_superuser` |

Two decisions are recorded here rather than left implicit:

**Content Admin becomes its own account type.** The product document gives it a bounded remit — validate metadata, rights, document status and publication — distinct from the super admin's platform configuration, billing and sensitive operations. Today both collapse into `platform_staff`, so a content moderator would receive billing and configuration power. A new value is cheaper and more legible than layering Django Groups onto a codebase that uses none.

**Sponsor Partner is not an account type.** Its described capabilities — funding access for a group and receiving agreed impact reporting — are those of an organization admin whose organization is a sponsor. Adding a fifth account type would duplicate the organization-scoped logic. The distinction lives on `Organization.organization_type`, where it already exists.

## Architecture

A single source of truth, consumed by three surfaces.

### Predicates

`accounts/permissions.py` holds plain predicate functions. They take a user, and an object when scope matters:

```python
is_platform_staff(user) -> bool
is_content_admin(user) -> bool                       # content admin or super admin
administers_organization(user, organization) -> bool
administered_organization_ids(user) -> list[int]

can_submit_document(user) -> bool                    # teacher/author, content admin
can_review_publication(user) -> bool                 # content admin
can_withdraw_document(user, document) -> bool        # own voluntary deposit, or content admin
can_manage_organization_members(user, organization) -> bool
can_view_organization_reports(user, organization) -> bool
can_manage_billing(user) -> bool                     # super admin only
```

They are pure reads over `accounts`, with no HTTP and no DRF, so services, the API and the admin all ask the same question and get the same answer. `administers_organization` reuses `active_organization_ids_for_user`, so a suspended membership or an unverified identity removes administrative authority exactly as it removes reading access.

### API

`api/v1/permissions.py` wraps the predicates in DRF permission classes (`IsContentAdmin`, `IsTeacherOrContentAdmin`, `AdministersOrganization`). Views declare them instead of relying on `IsAuthenticated` alone. A refusal returns the standard error envelope with code `permission_denied`.

### Django Admin

Admin classes gain `has_add_permission`, `has_change_permission` and `has_delete_permission` derived from the same predicates, so a content admin can moderate publication without inheriting billing or configuration. `AuditLogAdmin` keeps its existing append-only stance.

This is where the current `is_staff` boolean is replaced as the real gate: `is_staff` continues to decide whether the admin site opens at all, while the predicates decide what is visible and editable inside it.

### Audit

`record_publication_decision` and `resolve_support_ticket` already audit. Membership changes and entitlement grants made under a role do not, and will: every state-changing action reachable through a role records an event with the actor, the target and the reason.

## Boundaries To Enforce

Straight from the product document, each one a test:

- An institution admin invites, approves, suspends and removes members **of their own organization**, and is refused on any other.
- An institution admin cannot publish or withdraw a document, change document rights, alter contracts or pricing, or modify platform roles.
- An institution admin sees aggregate reports for their organization, never a personal reading history.
- An institution admin cannot see documents in private processing states.
- A teacher/author submits documents and requests withdrawal of their own voluntary deposits; institutional-fund documents follow the contract and are refused.
- A teacher/author cannot approve their own submission.
- A content admin validates publication but cannot manage billing or platform configuration.
- A student and a visitor hold no management capability whatsoever.

## Migration

Adding `CONTENT_ADMIN` to `AccountType` is a choices change plus a migration. No existing row changes meaning: current `platform_staff` accounts stay super admins, which is the safe direction. Promoting someone to content admin is a deliberate act.

`seed_demo` gains a content-admin account so the deposit slice has a reviewer to work with.

## Testing

Use pytest and pytest-django. Tests must prove:

- each predicate answers correctly for each of the seven actors, including the two negative-by-construction ones (visitor, student);
- organization scope holds: an admin of organization A is refused on organization B;
- a suspended membership, an ended membership, or an unverified identity in a verification-required organization removes administrative authority;
- every boundary in the section above is refused for the wrong actor, with the standard error envelope and code;
- admin classes refuse add, change and delete to actors without the matching predicate;
- role-bearing state changes record an audit event naming the actor;
- entitlement-based reading is unchanged — a role grants no reading access, and the existing reader tests still pass untouched.

## Out Of Scope

- The upload endpoint, the deposit screen and the publication workflow UI (next slice).
- An institution dashboard or any organization-facing frontend.
- Invitation emails, onboarding flows and identity-proof upload.
- Object-level permissions beyond organization scope.
- Reader hardening: page images in the reader, signed URLs, device limits. All three are Phase 2.
- Row-level security in the database.
