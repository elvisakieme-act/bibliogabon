# BiblioGABON Catalog Metadata Design

## Purpose

This slice creates the backend catalog foundation for BiblioGABON: academic domains, authors, document metadata, rights agreements, and publication status rules. It does not ingest files, expose raw files, render pages, implement search, or build the reader. Those subsystems will consume the catalog records created here.

## Product Rules

BiblioGABON is a national academic digital library for Gabon. The default catalog is national and shared; organizations finance access but do not own isolated catalogs by default. Public metadata may be visible to visitors unless a document is private. Restricted reading later requires an active entitlement, and document-specific entitlements must be compatible with `accounts.Entitlement.ScopeType.DOCUMENT`.

Every publishable document must have explicit governance data before publication:

- an owner or rights holder;
- a document category;
- an access model;
- a withdrawal rule;
- at least one author;
- a publication status.

Raw PDF/EPUB files remain outside this slice and must never become public URLs.

## Architecture

Create a focused Django app named `catalog`. It owns catalog and publication metadata only. The existing `accounts` app remains responsible for identities, organizations, memberships, and entitlements.

Core models:

- `AcademicDomain`: hierarchical subject area such as Law, Medicine, Computer Science, or Education.
- `Author`: academic contributor identity, optionally linked to a platform `User`.
- `Document`: intellectual resource metadata and publication lifecycle state.
- `DocumentAuthor`: ordered relation between documents and authors.
- `RightsAgreement`: rights and publication governance record attached to one document.

`Document` exposes `entitlement_scope_id` as `str(document.pk)` so access checks can call:

```python
user_has_entitlement(
    user,
    Entitlement.AccessRight.READ,
    scope_type=Entitlement.ScopeType.DOCUMENT,
    scope_id=document.entitlement_scope_id,
)
```

## Publication Behavior

Publication statuses follow the governance sequence:

```text
draft -> submitted -> rights_review -> technical_processing -> editorial_review -> published -> withdrawn -> archived
```

The catalog also supports `rejected` for rights-review refusal and `suspended` for urgent confidentiality or complaint handling. These are controlled publication states, not reader-session behavior.

This slice enforces publication readiness with a service function:

```python
document_is_publishable(document) -> bool
```

A document is publishable only when it has a title, academic domain, at least one author, and a valid rights agreement. The function does not change state; workflow transitions and audit logs will be built later.

`RightsAgreement` stores the declarative governance fields needed now: agreement type, rights holder, authorization status, authorization date, access model, withdrawal rule, confidentiality terms, consent reference, reviewer decision, rejection reason, and audit reference.

## Testing

Use pytest and pytest-django. Tests must prove:

- catalog app is installed;
- academic domains support hierarchy and unique slugs;
- documents can store required metadata and ordered authors;
- documents without rights governance are not publishable;
- complete rights governance makes a document publishable;
- document-specific entitlements work through the existing `accounts` service;
- catalog models are registered in Django admin.

## Out Of Scope

- File upload and private object storage.
- OCR, EPUB/PDF processing, page rendering, and generated assets.
- Full-text search.
- Billing, quotas, and subscriptions.
- Reader sessions, signed URLs, offline packages, and anti-download controls.
- Revenue-sharing calculation.
