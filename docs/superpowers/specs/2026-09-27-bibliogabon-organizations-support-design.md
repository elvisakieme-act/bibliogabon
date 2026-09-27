# BiblioGABON Organizations, Quotas And Support — Design

Slice 4 of 4 of `docs/superpowers/specs/2026-09-27-bibliogabon-back-office-design.md`.
Closes the rest of plan directeur §8.2, and with it "back-office minimum complet".

## Purpose

§8.2 names four things this slice must deliver:

> Gestion des organisations : quotas, utilisateurs rattachés, contrats, rapports
> d'usage. Support utilisateur, signalement de document, demandes de retrait.

Like slice 3, almost all of the domain exists. `accounts.services` audits every
membership change; `billing.services` mints and revokes entitlements when a
quota activates or ends; `analytics.services.generate_institution_report`
produces a report and nobody can trigger it. What is missing is surface — and
one model field.

## The Missing Field

`SupportTicket` already links to a user, an organization, a document, a payment
and an entitlement. It has **no category**. So a document report and a
withdrawal request are indistinguishable from "my payment failed", and the
back-office cannot triage them apart.

That is not cosmetic. A withdrawal request leads to an act — a moderator
withdraws, or explains why not — while a support question leads to an answer.
Mixing them means a withdrawal request sits in a generic queue until someone
reads it carefully enough to notice what it is.

So: `SupportTicket.category` with `support`, `document_report`,
`withdrawal_request`. One field, no new model: the lifecycle is identical
(`open → in_progress → resolved`), only the intent differs, and the `document`
foreign key already carries the target.

## Who Creates What

A back-office that handles reports nobody can file is decoration. Two public
endpoints are therefore part of this slice, and only two:

- `POST /api/v1/documents/<id>/report/` — any authenticated reader signals a
  problem with a published document.
- `POST /api/v1/documents/<id>/withdrawal-request/` — an author asks for their
  deposit to be withdrawn.

Both are rate-limited by nothing yet, which is deliberate and recorded: rate
limiting belongs to launch hardening, not here, and adding a half-measure would
suggest the problem is solved.

The withdrawal *request* is not a withdrawal. It creates a ticket that a
moderator acts on with the existing `withdraw_document`, which demands a reason
and writes an audit event. An author who could withdraw directly would bypass
the contract rules `can_withdraw_document` encodes — and the request path is
precisely what a contract-bound category needs.

## Organization Scope Is An Argument, Not A Filter

`administers_organization(user, organization)` already takes the organization
as an argument, so an institution admin is refused on any organization but
their own *at the predicate*. The endpoints must pass the organization they are
acting on, never trust a list filtered afterwards. A test asserts the refusal
at the endpoint, not only in the predicate — the two can drift.

An institution admin sees their organization's members, quotas and usage
report. They do not see the catalogue's review queue, other organizations, or
any per-user reading record. The last point is a product rule, not an
implementation detail: institutional analytics aggregate to
`DailyUsageAggregate`, and a report that named who read what would turn a
library into a surveillance tool.

## What The Report Must Not Contain

`generate_institution_report` already aggregates. Exposing it adds one risk:
the report is the one staff payload built from reading activity. The endpoint
returns `InstitutionReport.metrics` as produced, and a test scans it for any
per-user field. If a future metric adds one, the test fails rather than the
leak shipping.

## Architecture

### Services

Two additions in `operations/services.py`, shaped like the existing ones:

```python
report_document(*, document, reason, reported_by, at=None) -> SupportTicket
request_document_withdrawal(*, document, reason, requested_by, at=None) -> SupportTicket
```

Both refuse an empty reason and an absent actor, for the same audit reason
withdrawal does. Both write an audit event. `request_document_withdrawal`
refuses a document that is not published: there is nothing to withdraw from a
draft, and accepting the request would promise an act that cannot happen.

Organization membership and quota changes reuse `accounts.services` and
`billing.services` unchanged. The slice adds no billing logic.

### Staff API

```
GET   /api/staff/v1/organizations/                    celles qu'on administre
GET   /api/staff/v1/organizations/<id>/               une, avec ses compteurs
GET   /api/staff/v1/organizations/<id>/members/       les adhésions
POST  /api/staff/v1/organizations/<id>/members/       rattacher
POST  /api/staff/v1/organizations/<id>/members/<id>/suspend/
POST  /api/staff/v1/organizations/<id>/members/<id>/end/
GET   /api/staff/v1/organizations/<id>/quotas/        quotas et contrats
GET   /api/staff/v1/organizations/<id>/report/        rapport d'usage d'une période
GET   /api/staff/v1/tickets/                          support, signalements, retraits
GET   /api/staff/v1/tickets/<id>/
POST  /api/staff/v1/tickets/<id>/assign/
POST  /api/staff/v1/tickets/<id>/resolve/
```

The ticket queue is visible to platform staff and content admins. An
organization admin sees only tickets attached to their own organization —
scoped by the same predicate, passed as an argument.

### Screens

`/gestion/organisations` and `/gestion/organisations/$id` — members with their
verification status, quotas with their contract references, and the usage
report for a chosen period. The verification status matters visually: an
unverified membership grants nothing, and an admin who does not see that will
not understand why a member cannot read.

`/gestion/support` — the queue, filtered by category and status, with the
resolution form. A withdrawal request shows a link to the document and says
plainly that resolving the ticket does not withdraw anything: the moderator
must act on the document.

## Testing

Beyond the rules that hold across all four slices:

- an institution admin is refused on another organization, at every endpoint;
- an institution admin sees no per-user reading record in their report;
- the usage report payload is scanned for per-user fields, so a future metric
  that adds one fails the test instead of leaking;
- a reader may report a published document, and may not report a draft — which
  would confirm that the draft exists;
- an author may request withdrawal of their published deposit; the request
  creates a ticket and withdraws nothing;
- resolving a withdrawal-request ticket does not change the document;
- suspending a membership removes reading access immediately, and the endpoint
  reuses the audited service rather than writing the field;
- every membership and quota change writes an audit event.

## Out Of Scope

- Rate limiting on the public report endpoints — launch hardening.
- Notifications. A moderator sees the queue; nobody is emailed.
- Self-service organization signup, contract upload, invoicing documents.
- Quota purchase flows: the back-office reads quotas and activates them through
  the existing service; selling them is a commercial flow, not §8.2.
- Per-user analytics of any kind, at any level. Not deferred — excluded.
