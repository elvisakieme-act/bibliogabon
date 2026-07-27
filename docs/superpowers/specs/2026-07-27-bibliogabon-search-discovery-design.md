# BiblioGABON Search And Discovery Design

## Purpose

This slice creates the first search and discovery foundation for BiblioGABON. It lets public clients discover published academic documents through safe metadata search, while keeping reader access, entitlements, storage assets, and page text exposure under the existing reader rules.

The implementation is deliberately database-backed. It avoids Elasticsearch, Meilisearch, PostgreSQL full text search, background workers, analytics, recommendations, and faceted UX work until the product has stable content volume and usage signals.

## Product Rules

A document is discoverable when `catalog.Document.publication_status` is `published` and `catalog.Document.access_model` is not `private`.

Public search may expose document metadata for restricted documents. It must not expose private documents, unpublished documents, withdrawn documents, suspended documents, source storage keys, generated asset keys, public URLs, signed URLs, download URLs, reader session keys, or raw page text snippets.

Extracted page text can be indexed internally to improve search matching. When a query matches only page text, the API may indicate that text contributed to the match, but it must not return the matching text. Reading the content still goes through `document_reader`.

## Architecture

Create a Django app named `search_discovery`. It depends on `catalog`, `document_ingestion`, and `document_processing`. None of those apps import `search_discovery`.

Core model:

- `DocumentSearchIndex`: one row per discoverable document, denormalizing safe metadata plus internal aggregate page text.

Primary services:

```python
document_is_discoverable(document) -> bool
rebuild_document_search_index(document) -> DocumentSearchIndex | None
rebuild_all_document_search_indexes() -> int
search_documents(query="", domain_slug="", language_code="", access_model="", publication_year=None, limit=20) -> list[dict]
```

HTTP endpoint:

- `GET /search/documents/`

Supported query parameters:

- `q`: case-insensitive search over title, abstract, authors, domain, and internal page text; normalized length is capped at 120 characters.
- `domain`: exact academic domain slug.
- `language`: exact language code.
- `access`: exact access model.
- `year`: exact publication year.
- `limit`: positive integer capped at 50.

## Ranking

Ranking is deterministic and simple:

- title match: strongest signal;
- author match: strong signal;
- domain match: medium signal;
- abstract match: medium signal;
- internal page-text match: weak signal.

Results sort by score descending, then title ascending. Empty queries return discoverable indexed records sorted by title.

## API Payload

Each result includes only safe fields:

- `document_id`, `title`, `slug`, `abstract`;
- `language_code`, `publication_year`;
- `academic_domain` with `name` and `slug`, or `null`;
- `authors` as ordered display names;
- `access_model`;
- `indexed_page_count`;
- `score`;
- `text_match`.

No page text, storage data, asset URL, or reader authorization data appears in search payloads.

## Testing

Use pytest and pytest-django. Tests must prove:

- the app is installed;
- index rows store safe metadata, ordered authors, domain data, and internal page text;
- private and unpublished documents are not indexed;
- rebuilding a withdrawn, suspended, or private document removes its index row;
- page text is collected only from the current processed version and processed pages;
- query ranking favors title matches above body-only matches;
- filters work for domain, language, access model, publication year, and limit;
- public JSON search returns safe result payloads;
- invalid numeric query parameters return JSON errors;
- search models are registered in Django admin.

## Out Of Scope

- Full text search engines.
- PostgreSQL-specific search vectors.
- Query autocomplete and typo tolerance.
- Public page snippets.
- Reader session creation.
- Entitlement-gated search personalization.
- Search analytics and recommendations.
- Frontend search screens.
