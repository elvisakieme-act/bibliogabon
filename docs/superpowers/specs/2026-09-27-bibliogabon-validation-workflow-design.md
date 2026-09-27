# BiblioGABON Validation Workflow — Design

Slice 3 of 4 of `docs/superpowers/specs/2026-09-27-bibliogabon-back-office-design.md`.
Closes Phase 1's "workflow de validation".

## Purpose

A submitted document becomes published, or does not, through a decision that
names its author and its reason. Today `record_publication_decision` exists and
is tested, but nothing reaches it from outside a Python shell: no endpoint, no
screen, no queue. A moderator cannot see what is waiting.

Two transitions have no service at all. `withdrawn_at` exists as a field and is
only ever cleared; `archived` is unreachable. So the six states D014 settled on
are still, in practice, four.

## What Already Exists

Slice 3 adds surface, not domain. What it builds on:

- `operations.PublicationReview` — open / approved / rejected / cancelled, with
  `reviewer`, `decided_by`, `decision_reason`, `internal_notes`, and a `clean()`
  that refuses a closed review without `decided_at` and a rejection without a
  reason. The model already forbids the inconsistent states.
- `operations.AuditLog` — immutable by construction: `save` raises on an
  existing row, `delete` raises. An audit trail that can be edited is decor.
- `operations.services.open_publication_review` and
  `record_publication_decision` — the second locks both the review and the
  document with `select_for_update`, refuses to close a review twice, and
  refuses to approve a document that is not publishable.
- `catalog.services.missing_publication_requirements` — the rights gate, which
  D014 made the only representation of that gate.

## What Is Missing

**Withdrawal and archiving have no service.** The governance document is
precise about withdrawal, and the precision is the point:

> Withdrawal must be reversible internally. The public state changes, but
> processing records, audit logs, contracts, and metadata history remain
> available to authorized staff.

So withdrawal is not a deletion and not a soft-delete either. It sets
`publication_status` and `withdrawn_at`, keeps everything else, and records why.
Republication then requires a **new** decision — governance again: "Withdrawn
documents remain internally traceable and can be republished only through a new
validation decision." A withdrawn document therefore goes back through a review,
not through a flag flip.

**Archiving** is the end of a document's life on the platform. It is not
withdrawal: a withdrawn document may return, an archived one is closed. Both
stop reading, which `document_is_reader_accessible` already handles by testing
for `published`.

**Nothing exposes the audit trail.** `record_audit_event` writes faithfully and
no one can read it outside Django Admin, which shows raw JSON. A traceability
guarantee no one can consult is a guarantee on paper.

## Product Rules

Rights are verified before publication, and that verification lives in one
place. D014 removed the `rights_review` state precisely so that
`RightsAgreement.authorization_status` is the only answer to "were the rights
checked". The review screen therefore **shows** the rights status and refuses to
approve without it, but does not carry its own rights decision — that belongs to
the rights section of the deposit screen, where a content admin already decides.

A decision without a reason is not a decision. The model already requires one
for a rejection. The API requires one for a withdrawal too: a public document
disappearing without a recorded reason is exactly what an audit is for.

Separation of duties extends to review. A depositor does not review their own
deposit. `can_review_publication` is content-admin only, so a teacher-author
cannot reach the queue at all — but the endpoint must also refuse a content
admin who is *also* the document's author, otherwise the separation holds only
by luck of role assignment.

Withdrawal follows the category. `can_withdraw_document` already encodes it: a
content admin always may; a teacher-author may withdraw their own deposit unless
the category is contract-bound (`institutional_fund`,
`commercial_partner_content`), where a unilateral withdrawal would breach a
contract.

## Architecture

### Services

Two new functions in `operations/services.py`, shaped like
`record_publication_decision`:

```python
withdraw_document(*, document, reason, actor=None, at=None) -> Document
archive_document(*, document, reason, actor=None, at=None) -> Document
```

Both lock the document with `select_for_update`, refuse an empty reason, refuse a
transition that makes no sense (withdrawing a draft, archiving twice), set the
dates, and record an audit event naming the actor and the reason. They do not
touch `RightsAgreement`: a withdrawal is not a rights revocation, and conflating
them would make republication require a fresh rights approval it does not need.

`withdraw_document` clears nothing and deletes nothing — the stored file, its
pages and its index stay. Only `document_is_reader_accessible` changes its
answer, because it tests for `published`.

### Staff API

```
GET  /api/staff/v1/reviews/                    file d'attente
POST /api/staff/v1/reviews/                    ouvrir une revue
GET  /api/staff/v1/reviews/<id>/               une revue et son contexte
POST /api/staff/v1/reviews/<id>/assign/        se saisir du dossier
POST /api/staff/v1/reviews/<id>/decision/      approuver, rejeter, annuler
POST /api/staff/v1/documents/<id>/withdraw/    retirer, avec motif
POST /api/staff/v1/documents/<id>/archive/     archiver, avec motif
GET  /api/staff/v1/documents/<id>/audit/       journal d'audit du document
```

The queue is the only listing that is *not* scoped by authorship — a reviewer
must see what others deposited. It is scoped by role instead:
`can_review_publication`, content-admin only.

The audit endpoint is read-only and exposes `actor`, `event_type`, `summary`,
`created_at` and `metadata`. It filters `metadata` through an allow-list rather
than returning it whole: audit metadata is written by many services and one of
them could one day put a storage key in it. A privacy rule that depends on every
future writer being careful is not a rule.

### Screens

`/gestion/revues` — the queue, filterable by state and by assignment, showing
what each document is still missing for publication. A reviewer should see
*before* opening a file that its rights are not approved.

`/gestion/revues/$reviewId` — the document under review, its rights status, its
ingestion state, its pages count, and the decision form. The approve control is
disabled while `missing_for_publication` is non-empty, and the screen says which
requirement blocks it rather than only greying a button.

The withdrawal and archiving actions live on the document detail screen, next to
the state badge, because they apply to a document and not to a review. Each
opens a small form demanding a reason, and neither is reachable for a state where
it makes no sense.

The audit trail appears on the document detail screen as a chronological list:
who, what, when, why. It is the visible proof of the guarantee.

## Testing

Beyond the rules that hold across all four slices:

- a teacher-author is refused on the queue, the decision, and the audit trail;
- a content admin who authored the document is refused on its decision — the
  separation of duties must not depend on role assignment alone;
- approving a document whose rights are not approved is refused, at the endpoint
  and not only in the service;
- a rejection without a reason is refused; so is a withdrawal without one;
- withdrawing a published document keeps its pages, its version and its index —
  only its readability changes;
- a withdrawn document is not readable through either reader surface;
- republishing a withdrawn document requires a new review, and clears
  `withdrawn_at`;
- archiving a document that is already archived is refused;
- every transition writes exactly one audit event naming the actor and reason;
- the audit endpoint never returns a storage key, even if a future service
  writes one into metadata — the allow-list is tested with a deliberately
  poisoned event;
- the screens: the queue renders what blocks each document, the approve control
  is gated with a stated reason, a decision without a reason cannot be
  submitted, and the audit trail renders in order.

## Out Of Scope

- Notifications of any kind. A reviewer sees the queue; nobody is emailed.
- Reviewer workload balancing or automatic assignment.
- Bulk decisions. Ten documents approved in one click is exactly how an
  unexamined document gets published.
- Document reports and withdrawal *requests* from readers — slice 4.
- Reverting an audit event. It is immutable by construction and stays so.
