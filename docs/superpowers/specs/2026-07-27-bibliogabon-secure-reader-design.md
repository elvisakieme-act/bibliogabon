# BiblioGABON Secure Reader Design

## Purpose

This slice creates the first secure reader foundation for BiblioGABON. It allows an authenticated user to open a controlled reading session and request page text through an internal JSON API. It does not expose raw files, generated assets, public URLs, signed URLs, DRM, offline packages, or mobile-reader behavior.

## Product Rules

Reading is separate from publication and processing. A document can be read only when:

- `catalog.Document.publication_status` is `published`;
- the document access model is not `private`;
- a current `document_ingestion.DocumentVersion` is `processed`;
- the requested `document_processing.DocumentPage` is `processed`;
- extracted text exists for the page;
- the user is authenticated;
- restricted access models have an active `read` entitlement at request time.

`free` published documents do not require an entitlement, but still require an authenticated user in this backend slice. `subscription`, `institution_only`, `sponsored`, and `restricted` documents require `accounts.user_has_entitlement(user, read, document, document_id)` for both session start and every page read. This prevents expired or revoked entitlements from continuing to unlock restricted pages.

## Architecture

Create a dedicated Django app named `document_reader`. It depends on `accounts`, `catalog`, `document_ingestion`, and `document_processing`. None of those apps should import `document_reader`.

Core models:

- `ReaderSession`: a time-boxed reading session for one user, document, and document version.
- `PageAccessLog`: a successful page-read event tied to a reader session and page.

Primary services:

```python
start_reader_session(user, document, client_ip="", user_agent="", at=None) -> ReaderSession
end_reader_session(session, at=None) -> ReaderSession
get_reader_page(session, page_number, at=None) -> dict
```

HTTP endpoints use plain Django views and JSON responses:

- `POST /reader/documents/<document_id>/sessions/`
- `GET /reader/sessions/<session_key>/pages/<page_number>/`
- `POST /reader/sessions/<session_key>/end/`

## Validation

Sessions must reference a version belonging to the same document. Active sessions require a future `expires_at`. Ending a session records `ended_at`.

Page access must reject inactive, expired, or ended sessions. Restricted documents must re-check entitlement on every page request. Page payloads must include only reader-safe fields: document id, version id, session key, page number, page count, language code, and text.

## Testing

Use pytest and pytest-django. Tests must prove:

- the app is installed;
- reader sessions store user, document, version, expiry, and client metadata;
- unpublished and private documents cannot start reader sessions;
- published free documents can start sessions for authenticated users;
- restricted documents require active read entitlement at session start;
- expired entitlements stop restricted page reads even if the session was already open;
- inactive or expired sessions cannot read pages;
- missing, unprocessed, or textless pages are unavailable;
- successful page reads create `PageAccessLog`;
- JSON endpoints return the same authorization behavior without public, signed, or storage URL fields;
- reader models are registered in Django admin.

## Out Of Scope

- Anonymous free reading.
- Real page image streaming.
- Signed or presigned URL generation.
- DRM, watermarking, copy controls, screenshot controls, or offline packages.
- Device/session concurrency limits.
- Download permissions.
- Search and discovery APIs.
- Analytics dashboards and audit-log subsystem.
