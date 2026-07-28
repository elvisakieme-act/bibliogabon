# BiblioGABON Operations Admin Audit Final Fix Report

## Findings Fixed

1. Registered the publication review and support ticket workflow methods as real Django Admin actions.
   - `PublicationReviewAdmin.actions` now includes approve, reject, and cancel.
   - `SupportTicketAdmin.actions` now includes resolve.
   - Every workflow action declares `permissions=["change"]`.
   - Regression tests exercise `ModelAdmin.get_actions()` for staff users with and without model change permission.

2. Closed ORM update paths that could mutate append-only audit logs.
   - `AuditLogQuerySet.update()` and `bulk_update()` now reject mutation with `ValueError("Audit logs are immutable")`.
   - The custom queryset is used by both the default manager and `_base_manager`.
   - `AuditLog.actor` now uses `PROTECT` instead of `SET_NULL`.
   - Migration `operations/0003_alter_auditlog_actor.py` records the relation change.
   - `PROTECT` is required because Django's `SET_NULL` deletion collector applies its field change through `QuerySet.update()`. Protecting the actor preserves audit attribution and avoids conflicting with the immutable queryset contract.

3. Prevented valid 260-character document titles from breaking publication workflows.
   - Generated publication review audit summaries are deliberately truncated to the declared `AuditLog.summary` maximum length.
   - Direct callers of `record_audit_event()` retain the existing strict model validation; only generated publication summaries are normalized.
   - Opening and approval workflows are both covered with maximum-length title regressions.

## TDD RED/GREEN Evidence

### Finding 1: Admin Action Discovery

RED:

```text
> .\.venv\Scripts\python.exe -m pytest operations\tests\test_admin_registration.py -q
F..........                                                              [100%]
FAILED test_workflow_admin_actions_are_registered_for_users_with_change_permission
AssertionError: expected approve_reviews, reject_reviews, and cancel_reviews;
get_actions() returned dict_keys([])
1 failed, 10 passed in 16.83s
```

GREEN after explicit action registration and change-permission metadata:

```text
> .\.venv\Scripts\python.exe -m pytest operations\tests\test_admin_registration.py -q
...........                                                              [100%]
11 passed in 16.14s
```

### Finding 2: Audit Log ORM Immutability

RED:

```text
> .\.venv\Scripts\python.exe -m pytest operations\tests\test_audit_logs.py -q
...........FFFF                                                          [100%]
FAILED test_audit_log_cannot_be_updated_through_a_queryset
FAILED test_audit_log_cannot_be_updated_through_the_base_manager
FAILED test_audit_log_cannot_be_bulk_updated
FAILED test_audit_log_actor_is_protected_from_deletion
4 failed, 11 passed in 8.55s
```

The three update tests failed because no `ValueError` was raised. The actor test failed because deletion used `SET_NULL` instead of raising `ProtectedError`.

GREEN after queryset guards, `PROTECT`, and migration generation:

```text
> .\.venv\Scripts\python.exe -m pytest operations\tests\test_audit_logs.py -q
...............                                                          [100%]
15 passed in 7.97s
```

### Finding 3: Maximum-Length Document Titles

RED:

```text
> .\.venv\Scripts\python.exe -m pytest operations\tests\test_publication_reviews.py -q
..F.F..                                                                  [100%]
FAILED test_open_publication_review_truncates_audit_summary_for_max_length_title
ValidationError: summary has 290 characters; maximum is 240
FAILED test_publication_decision_truncates_audit_summary_for_max_length_title
ValidationError: summary has 292 characters; maximum is 240
2 failed, 5 passed in 15.00s
```

GREEN after truncating generated publication summaries:

```text
> .\.venv\Scripts\python.exe -m pytest operations\tests\test_publication_reviews.py -q
.......                                                                  [100%]
7 passed in 13.64s
```

## Commands and Outputs

Changed-behavior targeted suite:

```text
> .\.venv\Scripts\python.exe -m pytest operations\tests\test_admin_registration.py operations\tests\test_audit_logs.py operations\tests\test_publication_reviews.py -q
.................................                                        [100%]
33 passed in 31.00s
```

Full operations suite:

```text
> .\.venv\Scripts\python.exe -m pytest operations\tests -q
........................................                                 [100%]
40 passed in 38.79s
```

Django system check:

```text
> .\.venv\Scripts\python.exe manage.py check
System check identified no issues (0 silenced).
```

Migration consistency:

```text
> .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
No changes detected
```

Diff validation:

```text
> git diff --check
Exit code: 0
```

Git emitted only the checkout's existing LF-to-CRLF conversion warnings; it reported no whitespace errors.

## Files Changed

- `backend/operations/admin.py`
- `backend/operations/models.py`
- `backend/operations/services.py`
- `backend/operations/migrations/0003_alter_auditlog_actor.py`
- `backend/operations/tests/test_admin_registration.py`
- `backend/operations/tests/test_audit_logs.py`
- `backend/operations/tests/test_publication_reviews.py`
- `.superpowers/sdd/2026-07-28-bibliogabon-operations-admin-audit/final-fix-report.md`

## Self-Review

- Verified actions through Django's real discovery path, not by directly calling decorated methods.
- Verified users without change permission do not receive workflow actions.
- Verified mutation prevention through the default manager, base manager, and bulk update API.
- Verified actor deletion is rejected before audit attribution can be changed.
- Kept summary truncation scoped to generated publication messages and tied the limit to the model field declaration.
- Confirmed the migration matches the model state.
- Did not implement any deferred minor or out-of-scope surface.

## Concerns

No unresolved concerns. Deployments must apply migration `operations.0003_alter_auditlog_actor`; after it is active, users referenced as audit actors cannot be hard-deleted, which is the intended append-only attribution behavior.
