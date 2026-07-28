# BiblioGABON Operations Admin Audit Design

## Purpose

This slice creates the internal operations foundation for BiblioGABON. It gives administrators a reliable way to trace sensitive actions, review publication decisions, and handle user or institutional support cases from Django Admin.

It does not create a custom back-office UI, notification system, public support portal, or analytics dashboard. The goal is an operationally useful internal backend layer that can support launch and future product interfaces.

## Product Rules

Operational work must be traceable. Sensitive actions such as publication decisions, entitlement changes, organization role changes, payment handling, and support resolutions must leave a durable audit record.

Moderation and support records should reference existing domain objects where possible: users, organizations, documents, payments, and entitlements. They must not duplicate the source of truth owned by other apps.

Django Admin is the first back-office surface. It should be searchable, filterable, and safe for staff users. High-risk operational records should expose read-only metadata rather than encouraging direct database edits.

## Architecture

Create a Django app named `operations`. It may depend on `accounts`, `catalog`, and `billing`, but other apps should not need to import it directly except through small service functions.

Core models:

- `AuditLog`: immutable event record for sensitive administrative or system actions.
- `PublicationReview`: moderation workflow around a `catalog.Document`.
- `SupportTicket`: internal support case linked to a user, organization, document, or payment.

Primary services:

```python
record_audit_event(...) -> AuditLog
open_publication_review(...) -> PublicationReview
record_publication_decision(...) -> PublicationReview
open_support_ticket(...) -> SupportTicket
resolve_support_ticket(...) -> SupportTicket
```

## Audit Events

`AuditLog` records who did what, when, and to which object. It should store:

- `actor`: optional user for staff or system-triggered events;
- `event_type`: stable machine-readable action key;
- `target_app`, `target_model`, and `target_id`;
- `summary`: short human-readable description;
- `metadata`: structured JSON for contextual details;
- `created_at`: immutable timestamp.

Audit logs are append-only. Admin users may search and filter logs but should not edit or delete them through Django Admin.

## Moderation Workflow

`PublicationReview` tracks document review state independently from the document itself. Initial statuses are `open`, `approved`, `rejected`, and `cancelled`.

Each review links to one document, can be assigned to a reviewer, and stores the final decision, decision reason, and decision timestamp. Approving or rejecting a review should create an audit event. The slice may update document publication fields only through explicit service functions, not direct admin-side mutation.

## Support Workflow

`SupportTicket` tracks operational support requests. Initial priorities are `low`, `normal`, `high`, and `urgent`. Initial statuses are `open`, `in_progress`, `waiting`, `resolved`, and `cancelled`.

Tickets may link to one or more relevant context fields: user, organization, document, payment transaction, or entitlement. Resolution should store a short outcome and create an audit event.

## Admin Behavior

Register all operations models in Django Admin with:

- clear `list_display` columns for status, priority, actor, target, assignee, and timestamps;
- `list_filter` for status, priority, event type, decision, and dates;
- `search_fields` for user email, organization name, document title, payment reference, and summaries;
- `readonly_fields` for audit metadata and immutable timestamps.

`AuditLogAdmin` should block add, change, and delete operations. Review and ticket admins may allow normal edits for workflow fields, but service functions remain the preferred path for state transitions.

## Testing

Use pytest and pytest-django. Tests must prove:

- the `operations` app is installed;
- audit events can be recorded with actor, target, summary, and metadata;
- audit logs are not editable or deletable through admin permissions;
- publication reviews can be opened and resolved with audit records;
- support tickets can be opened and resolved with audit records;
- admin classes register the operations models with useful search, filter, and readonly settings.

## Out Of Scope

- Custom React or product admin interface.
- Public support request forms.
- Email, SMS, or in-app notifications.
- Full approval queues with SLAs and escalation rules.
- Fraud detection or compliance reporting.
- Analytics dashboards and institutional reporting.
- Object-level staff permission policy beyond Django Admin basics.
