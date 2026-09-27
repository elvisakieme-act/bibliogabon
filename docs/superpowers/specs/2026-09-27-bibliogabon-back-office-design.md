# BiblioGABON Back-Office Design

## Purpose

This document frames the production back-office described in `BiblioGABON_Plan_directeur_produit_startup.md` §8.2: a real interface for the people who run the library, not the Django admin the team has been using. It covers a staff API and the screens that consume it, delivered as four slices, and it closes Phase 1 of the launch roadmap.

It is a programme-level design. Each slice gets its own implementation plan.

## Why This Slice Exists

Phase 1 asks for a "back-office minimum complet". What exists is Django Admin, and the July operations spec was explicit about its own status:

> "Django Admin is the **first** back-office surface."
> Out of scope: "Custom React or product admin interface."

The frontend V1 spec deferred staff workflows in the same way, and the API V1 spec put "Staff/content admin API" out of scope. So the product back-office was deferred three times and never planned. Marking that line complete on the strength of Django Admin was wrong: the admin exposes storage keys, checksums and raw JSON, has no task-oriented flow, and depositing one document there means filling five unrelated model forms and then running a shell command.

Django Admin does not go away. It stays what it has actually been — a developer and operations surface — and this document stops treating it as the product's back-office.

## Product Rules

The back-office is for staff, and staff authority comes from roles. The predicates added on 2026-09-27 are the gate: a content admin reviews, a teacher deposits, a super admin manages billing, an institution admin acts on their own organization and nothing else.

Raw files never become public. An upload lands in private storage through the existing ingestion path; the back-office shows metadata, pages and status, never a storage key or a download link to the source.

Every state change is audited. The workflow exists to be traceable, so a transition without an actor and a reason is a bug.

Nothing in the back-office grants reading access. A reviewer looking at a document sees it because their role allows review, not because an entitlement was silently created.

## A Discrepancy — Settled By D014

> **Tranché le 27/09/2026 : cinq états, plus le rejet.** Ce qui suit reste
> pour la trace du raisonnement. La découverte décisive est venue plus tard :
> le désaccord n'était pas entre le code et le plan directeur, mais entre le
> plan directeur (cinq) et `docs/product/02-content-rights-governance.md`
> (dix), qui a été écrit pendant la conception. Et les trois états de revue
> dupliquaient des verrous déjà tenus ailleurs, et mieux.

`catalog.Document.PublicationStatus` carries ten states:

```
draft → submitted → rights_review → technical_processing → editorial_review → published → withdrawn → archived
                                                          plus rejected and suspended
```

The plan directeur §8.2 names five: "brouillon, en vérification, publié, retiré, archivé".

Today `record_publication_decision` jumps straight from any state to `published` or `rejected`, so six of the ten are unreachable. The back-office is where this gets resolved, and the choice belongs to the product owner:

- **Drive all ten.** Rights review and editorial review become separate gates with separate reviewers, matching the governance document's insistence that rights are verified before publication.
- **Collapse to the five named in §8.2**, and treat `rights_review`, `technical_processing` and `editorial_review` as substates of "en vérification".

The first slice must not guess. It carries the states it needs for deposit — `draft`, `submitted` — and the review slice settles the rest with an explicit decision recorded in the register.

## Architecture

### Staff API

A separate namespace, `/api/staff/v1/`, with its own OpenAPI schema.

Not `/api/v1/staff/`: the public contract promises that endpoints never reveal whether a private or unpublished document exists, and it serves a browser app, future mobile clients and partner integrations. The staff API contradicts both — it exists precisely to show unpublished work — and it should be free to change at a different pace. One schema mixing the two would document internal endpoints to the public and tie their versions together.

It reuses everything already built: `ingest_document_file` for deposit, `record_publication_decision` for review, the audited membership services for organizations, and the role predicates for authorisation. The staff API adds serialization, validation and HTTP shape, nothing else — the same discipline as `api/v1/`.

### Back-office interface

The same React application, under `/gestion`, consistent with the French route names already in use. The bundle is lazy-loaded so a reader never downloads it, and the whole area sits behind a role guard.

Reusing the app rather than starting a second one keeps one design system, one API client, one auth session and one build. The staff screens are denser than the reader screens and may diverge visually, which is expected: the maquette's editorial language serves discovery, not data entry.

### File upload

The one genuinely new mechanism. `multipart/form-data` on a single endpoint, streamed into `ingest_document_file`, which already hashes in one pass and writes in a second without materialising the file. Limits — maximum size, accepted MIME types — are configuration, and a refusal is a typed error, not a stack trace.

## The Four Slices

Each delivers a screen someone can use, so the back-office is never a half-built thing waiting on the next slice.

**1. Staff API foundation and document deposit.** The namespace, its schema, role-guarded routing, and the endpoints to create a document, attach authors and rights, upload a file, and follow ingestion status. Closes the "dépôt documentaire" half of Phase 1's third line at the API level, and makes the shell command optional.

**2. Back-office: deposit and catalogue.** The first screens — a deposit form, a document list with real filters, a document detail showing metadata, rights, versions, pages and ingestion state. A teacher can deposit without a terminal.

**3. Back-office: validation workflow.** The review queue, the transitions, the rights checks, the decision with its reason, and the audit trail made visible. Settles the ten-versus-five question. Closes "workflow de validation".

**4. Back-office: organizations, quotas and support.** Members, quotas, contract references, usage reports scoped to one organization, support tickets, document reports and withdrawal requests. Closes the rest of §8.2, and with it "back-office minimum complet".

## Testing

Each slice carries its own tests; the rules that hold across all four:

- every staff endpoint refuses the wrong role, with the standard error envelope;
- an institution admin is refused on any organization but their own, at the endpoint and not only in the predicate;
- no staff response exposes a storage key, a signed URL or a source download link;
- every state transition records an audit event naming the actor and the reason;
- an upload that exceeds the size limit or carries an unaccepted type is refused as a typed error;
- the reader-facing API and its tests are untouched: the public contract does not move because a staff surface appeared.

## Out Of Scope

- Replacing or removing Django Admin, which stays a developer and operations surface.
- A teacher-facing contributor space beyond deposit: usage tracking, author identity management, public profiles.
- Institution-facing dashboards for organization members; slice 4 serves staff and organization admins, not end users.
- Notifications of any kind — email, SMS, in-app.
- Bulk import, batch ingestion and archive migration.
- EPUB.
- Reader hardening: page images in the reader, signed URLs, device limits. All three remain Phase 2.
