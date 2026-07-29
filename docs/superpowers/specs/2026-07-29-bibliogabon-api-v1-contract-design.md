# BiblioGABON Public API V1 Contract Design

## Purpose

This slice defines the first public REST JSON API contract for BiblioGABON. It turns the existing Django backend domains into a stable `/api/v1/` surface for the future web frontend, mobile clients, and controlled partner integrations.

The API prioritizes the student/reader experience: account creation, authentication, public discovery, document details, secure reading, favorites, and minimal reading progress. Staff workflows, ingestion, publication review, rights administration, reporting, and institutional management remain in Django Admin for now.

## Product Decisions

- The API is public, documented, versioned, and JSON-only.
- V1 uses REST under `/api/v1/`.
- Authentication uses JWT, not Django session auth, for API clients.
- Individual user registration is open to the public.
- Public registration creates only an individual learner account. Teacher, institution admin, content admin, and platform staff roles are assigned through internal workflows.
- Public catalog and search endpoints can be used anonymously.
- Free or open-access documents can be read anonymously through the secure reader.
- Restricted documents require JWT authentication and an active read entitlement.
- Raw files, storage keys, signed URLs, OCR full text, payment metadata, personal reading history, and private admin data are never exposed through catalog or search payloads.

## Technical Approach

Add Django REST Framework, SimpleJWT, and drf-spectacular. Keep API code in a dedicated `api` package with versioned routing:

```text
backend/
  api/
    v1/
      auth.py
      serializers.py
      urls.py
      views.py
      tests/
```

Existing domain apps remain the source of truth. API views must call existing app services when those services enforce business rules, especially for search visibility and reader access. The API layer owns serialization, request validation, response shape, authentication, permissions, and OpenAPI annotations.

## API Domains And Endpoints

Authentication:

```text
POST /api/v1/auth/register/
POST /api/v1/auth/token/
POST /api/v1/auth/token/refresh/
POST /api/v1/auth/logout/
```

Current user:

```text
GET   /api/v1/me/
PATCH /api/v1/me/
```

Catalog and discovery:

```text
GET /api/v1/catalog/documents/
GET /api/v1/catalog/documents/{id}/
GET /api/v1/catalog/domains/
GET /api/v1/catalog/authors/
GET /api/v1/search/
```

Reader:

```text
POST   /api/v1/reader/sessions/
GET    /api/v1/reader/sessions/{session_key}/pages/{page_number}/
DELETE /api/v1/reader/sessions/{session_key}/
```

Personal library:

```text
GET    /api/v1/me/favorites/
POST   /api/v1/me/favorites/
DELETE /api/v1/me/favorites/{document_id}/
GET    /api/v1/me/reading-progress/
PATCH  /api/v1/me/reading-progress/{document_id}/
```

Schema and docs:

```text
GET /api/v1/schema/
GET /api/docs/
```

## Response Standards

Use stable JSON envelopes for list responses:

```json
{
  "count": 25,
  "next": "https://example.com/api/v1/catalog/documents/?page=2",
  "previous": null,
  "results": []
}
```

Use predictable error payloads:

```json
{
  "error": {
    "code": "entitlement_required",
    "message": "An active read entitlement is required.",
    "field_errors": {}
  }
}
```

Use explicit status codes: `200`, `201`, `204`, `400`, `401`, `403`, `404`, `409`, and `429` where applicable.

## Catalog Contract

Document lists and detail responses expose safe metadata only:

- id, slug, title, abstract;
- language, publication year, document type, access model;
- domain, authors, owner display label when public;
- page count when available;
- cover as `null` or an approved public thumbnail URL, never a raw asset key or private storage URL;
- contextual `access` block when a user is authenticated.

Example access block:

```json
{
  "access": {
    "can_read": true,
    "access_model": "subscription",
    "reason": "active_entitlement"
  }
}
```

Anonymous responses may include `can_read=true` only for free or open-access documents.

## Reader Contract

The reader API is the only public route that returns document content. It never returns raw source files. It creates a short-lived reading session and returns page-safe payloads: document id, page number, page count, language, text or page-render metadata, and expiry information.

For restricted documents, every session creation and page request must re-check JWT identity and active read entitlement. For anonymous free reading, the reader still uses controlled sessions so rate limiting, expiry, and abuse controls can be added without changing the public contract. This V1 contract deliberately expands the earlier internal reader slice, which required authentication even for free documents.

## Favorites And Reading Progress

Favorites require authentication. A favorite links the current user to one published, discoverable document.

Reading progress also requires authentication and stores only resume-oriented data:

- document id;
- last page number;
- updated timestamp.

The API must not expose detailed page-by-page reading logs. Institutional and product analytics remain aggregated through existing analytics services.

## OpenAPI Documentation

drf-spectacular generates the schema at `/api/v1/schema/`. Swagger UI is available at `/api/docs/` for development and controlled internal review. Production exposure of Swagger UI can be disabled later without removing the schema endpoint.

Every public endpoint must include request and response examples, authentication requirements, and error codes in the generated schema.

## Security And Privacy

- JWT access tokens are short-lived; refresh tokens are longer-lived and revocable.
- Logout revokes or blacklists refresh tokens.
- Production requires HTTPS.
- Public endpoints must not reveal whether private or unpublished documents exist.
- Search can use internal full text for ranking, but responses must not leak OCR text snippets in V1.
- API logs must not include passwords, tokens, raw request bodies, signed URLs, payment metadata, or personal reading details.

## Testing

Use pytest and pytest-django. Tests must cover:

- API package and `/api/v1/` routing;
- user registration creates an individual account and rejects duplicate email;
- JWT login, refresh, and logout behavior;
- public catalog/search visibility rules;
- restricted documents do not expose content without entitlement;
- anonymous free reading works through the reader API;
- authenticated restricted reading requires active, non-revoked entitlement;
- favorites require authentication and are idempotent;
- reading progress stores only resume data;
- list pagination and normalized error payloads;
- OpenAPI schema and docs routes exist.

## Out Of Scope

- Partner API keys and scoped third-party access.
- Institution admin API.
- Staff/content admin API.
- Payment checkout API.
- Ingestion and publication workflow API.
- Native mobile push notifications.
- GraphQL.
- Public full-text snippets.
- Download, offline package, watermark, or DRM APIs.
