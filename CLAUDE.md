# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

BiblioGABON — national academic digital library for Gabon. Django 5 / DRF backend (`backend/`) + React 19 / Vite reader web app (`frontend/`). Product docs, specs, plans and runbooks live in `docs/`. Product language is French (UI copy, some code comments, docs); code identifiers are English.

## Commands

Backend (run from `backend/`). On this Linux studio Django is already on `PATH`, so use plain `python`; `README.md` and `AGENTS.md` document the Windows `.\.venv\Scripts\python.exe` form used on the author's machine — translate accordingly.

```bash
python -m pytest -q                              # full suite (~427 tests, ~3 min)
python -m pytest api/v1/tests -q                 # one app's tests
python -m pytest catalog/tests/test_x.py::test_y # single test
python -m ruff check .                           # lint
python -m ruff format .                          # format
python manage.py check
python manage.py makemigrations --check --dry-run  # CI fails if migrations are uncommitted
python manage.py migrate
python manage.py runserver
python manage.py spectacular --file schema.yml   # export OpenAPI
python manage.py seed_demo                       # idempotent demo dataset (dev only)
python manage.py ingest_file <document_id> file.pdf  # --sync with no worker, --replace to overwrite
python -m celery -A config worker -l info            # ingestion worker (needs CELERY_BROKER_URL)
```

Frontend (run from `frontend/`):

```bash
npm run format  # prettier
npm run dev     # vite, host and port from .env (see .nvmrc for the Node version)
npm run test    # vitest
npm run lint    # eslint
npm run build   # tsc --noEmit + vite build
```

CI (`.github/workflows/ci.yml`) runs: backend `ruff check` → `ruff format --check` → `check` → `makemigrations --check` → `pytest`; frontend `format:check` → `lint` → `test` → `build`. Run all of them before claiming work is done.

Layout belongs to the formatters — `ruff format` and Prettier. `E501` is disabled in `ruff.lint` on purpose: the formatter already keeps code within the width, and what remains are string literals it deliberately does not break. Splitting a message by hand makes it ungreppable for nothing. Node is pinned by `frontend/.nvmrc`, which CI reads too: `node-version: "20"` once resolved to the latest 20.x in CI while a local 20.9 failed on `node:util.styleText`.

Development runs on **PostgreSQL**, like production. `DATABASE_URL` must be a real environment variable for the test suite — `config/pytest_env.py` neutralises `backend/.env`, so a suite started without it would fall back to SQLite **in silence**. It now refuses to start instead (`ALLOW_SQLITE_TESTS=1` to override deliberately), for the same reason `REQUIRE_OCR=1` turns skips into failures: 862 tests were once reported green "on PostgreSQL" while running on SQLite, and a query PostgreSQL rejects — `FOR UPDATE` on the nullable side of an outer join, from `select_for_update()` next to `select_related()` — was breaking subscription activation in production. SQLite ignores row locking outright and serialises writes, so it hides both the queries it wrongly accepts and the races between concurrent requests. SQLite still works for a quick check but the tiled reader breaks on it: the reader asks for dozens of images at once and SQLite locks the whole database on every write, which surfaces as a 500 on a tile and sends the search for the defect towards the tiling, which has nothing to do with it. Persistent database connections are kept **outside development only**: `runserver` makes a thread per request and never reuses it, so a connection held in reserve stays open for a dead thread — opening a 157-page document, whose reader asks for images in bursts, exhausted PostgreSQL's hundred connections in a minute, and the symptom was a 500 on the *catalogue*, at the other end of the application. Both sides need a `.env` copied from `.env.example`. The backend reads it at startup via `load_dotenv` in `config/settings.py` — it did **not** until 2026-09-28, so every local setting written there was silently inert, and a CORS symptom sent the diagnosis to the opposite end of the stack. A real environment variable always wins over the file; `DJANGO_ENV_FILE` points at another file, and empty loads none, which is how the tests observe default settings. API docs at `/api/docs/` (Swagger) and `/api/v1/schema/`.

## Architecture

### Layering (backend)

Business logic lives in `<app>/services.py`, never in views. Views are thin: parse input, call a service, map domain exceptions to an error response. Most apps (`accounts`, `catalog`, `billing`, `operations`, `analytics`, `document_processing`) have **no views or urls at all** — they are pure domain layers consumed by `api/v1/` and by other services. When adding behaviour, add a service function and test it directly against models; only then expose it.

The app sequence mirrors the plan sequence in `docs/technical/00-subsystem-plan-index.md`: identity → catalog → ingestion → processing → reader → search → billing → operations → analytics → hardening. Dependencies flow in that direction (e.g. `document_reader` imports `accounts`/`catalog`; never the reverse).

### Roles and entitlements are two different axes

Identity says who authenticates, **roles** say which actions are allowed, **entitlements** say which content is readable. A role never grants reading access and an entitlement never grants a management action; a test asserts both directions.

Role predicates live in `accounts/permissions.py` and are the single source of truth. `api/v1/permissions.py` wraps them for DRF and `accounts/admin_mixins.py` for Django Admin, so all three surfaces answer the same question. Organization scope is an *argument* to the predicate, never a filter applied afterwards, and reuses `active_organization_ids_for_user` — so a suspended, ended or unverified membership removes administrative authority exactly as it removes reading access.

The seven product actors map onto five account types plus the membership role: Sponsor Partner is an `ORGANIZATION_ADMIN` of an organization typed `sponsor`, not a type of its own. `CONTENT_ADMIN` is deliberately distinct from `PLATFORM_STAFF` so moderating content does not confer billing.

A Django model permission alone grants nothing in the admin — authority is role-only, otherwise assigning a permission would bypass the matrix. `is_staff` still decides whether the admin site opens at all; the mixins decide what is usable inside it, and `is_platform_staff` accepts `is_superuser` so a root account with a drifted `account_type` cannot lock itself out.

Membership changes and administrative grants go through audited services in `accounts/services.py` (`add_organization_member`, `suspend_organization_membership`, `end_organization_membership`, `grant_entitlement`). A grant refuses an empty reason.

### Entitlements are the access-control core

`accounts.Entitlement` is the single gate for restricted reads. It is scoped (`GLOBAL` / `DOMAIN` / `DOCUMENT` / `COLLECTION`) and time-bounded (`starts_at`, `ends_at`, `revoked_at`), and can be attached to a **user** or to an **organization** (org entitlements reach a user through an active, identity-verified `OrganizationMembership` — see `accounts.services.active_organization_ids_for_user`).

Nothing creates entitlements ad hoc: `billing/services.py` mints and revokes them when a `Subscription`, `OrganizationQuota`, or `SponsoredCampaign` activates/cancels/expires. Read checks go through `document_reader.services.user_can_read_document` (single document) or `readable_document_ids_for_user` (list pages — a batched version that avoids N+1 entitlement queries; keep the two in sync when access rules change).

`Document.access_model` decides whether a check is even needed: `FREE` is open, `PRIVATE` is invisible, and `SUBSCRIPTION`/`INSTITUTION_ONLY`/`SPONSORED`/`RESTRICTED` require a `READ` entitlement.

### Two reader surfaces

- `/api/v1/reader/...` (`api/v1/reader.py`) — JWT, the surface the frontend uses.
- `/reader/...` (`document_reader/views.py`) — Django-session/CSRF, plain `JsonResponse` with a flat `{"error": code}` body.

Both delegate to the same `document_reader/services.py`. A change to reader access rules must be made in the service and covered on both surfaces.

Reading is page-at-a-time by design: a `ReaderSession` is opened against a specific processed `DocumentVersion` with a TTL (`READER_SESSION_TTL_MINUTES`), every page fetch re-validates session liveness *and* current entitlement, and writes a `PageAccessLog`. Raw files, storage keys and signed URLs must never appear in any response.

A page is served in two parts, and both go through the same `_ensure_reader_session_can_read`: its **text** with the position of every word (`ExtractedText.word_boxes`, fractions of the page — never pixels, since the render width is a setting), and its **rendered image** at `…/pages/<n>/image/`. The image is the layout; the transparent word layer over it is what makes the page selectable, searchable and readable by a screen reader. Text and positions come from one PyMuPDF pass on purpose: two extractors would let a reader select a word absent from the indexed text. A page with no rendered image reports `"image": null` so the reader falls back to text rather than requesting a 404 per page.

What a reader may do with that text follows the **signed rights agreement**, not a global switch: `document_reader.services.text_layer_policy` answers `selectable` (open licence or open resource), `protected` (`user-select: none` plus copy/context-menu prevention — which costs neither screen readers nor find-in-page), or `withheld` (a confidentiality clause: the server ships no positions at all, so `words` is empty and the page is only its image). `selectable` and `protected` send the same text: blocking selection **deters**, it does not protect. Only `withheld` protects, and that is why it costs the screen reader. A document with no rights agreement is `protected` — the direction of the mistake matters, since erring towards `selectable` betrays a depositor.

The reader is full-screen. Its bar carries three things and no more — exit plus position on the left, the brand in the centre, a button opening the display-options modal on the right — because a bar that exposes every setting ranks them with the reading itself and leaves no room on a phone. Below `sm` the brand is hidden: at 390px the centre of the bar lands on the end of "Page 1 sur 3" and the name overlaps it; between a mark and a position, the decorative one gives way. No render test sees that — jsdom lays nothing out, so the browser capture is the check. Page turning lives **in the document**: arrows at the mid-height extremes in horizontal and two-page mode, draggable page corners in two-page mode only, and **nothing at all in vertical scroll**, where scrolling already does the job and a second way of doing it would mean the screen had not chosen. Three reading modes (vertical scroll, horizontal strip, two-page) and a zoom scale, persisted per viewer in `localStorage`. Pages load as they approach the viewport: fetching all 157 pages of a course at once would flood the connection *and* the access log — and the observation root must be **the scrolling container**, since a margin only widens the root and a page hidden by an ancestor's overflow stays hidden. Zoom changes the page's size, never `transform: scale`, which would grow the page without growing the scroll area. **Which page is being read is a per-mode question**, not a shared one: vertical takes the most visible page, batched per animation frame — taking the last observer to fire reported the last page of the document on open — while the horizontal strip takes the page nearest the centre, because several whole pages sit side by side there and "most visible" always meant the leftmost. That number is also what gets written as reading progress.

The reader is a **IIIF** client (D018). At ingestion each page is tiled to IIIF Image API level 0 — static tiles under `…/pages/NNNN/tiles/`, keyed exactly like the API's URLs so serving is a lookup, not a translation. Measured at 300 dpi: 54 objects and 249 kB per page, ~1.7 s to generate. Those tiles have **no database row** — their keys are deterministic, so re-ingestion removes them by prefix (`blob_storage.delete_prefix`); only the full-size page and the thumbnail are recorded, the latter serving as the catalogue cover so a grid of twenty covers doesn't cost twenty 300-dpi pages.

`info.json` is a promise: a viewer asks for **only** what is declared there. Declaring a tile or a size that was never produced leaves the page blank with no server error and nothing in the logs — which is exactly how the `sizes` list shipped broken once. Two tests, one at the storage layer and one over HTTP, walk every declared tile and every declared size. `tile_storage_key` validates each component instead of concatenating what the client sent (a `../` would otherwise leave the page's subtree — `FileSystemStorage` refuses it, the S3 backend does not) and normalises `w,` and `w,h`, which are two spellings of one image that different clients prefer.

The session **manifest** (`…/sessions/<key>/manifest`) is what makes this affordable: one request describes every page, its dimensions and its full image service. Without it a viewer laying out 157 pages reads 157 `info.json`, asks for authorisation 157 times, and logs the whole document as read before the reader turns a page. Its absolute URLs come from `PUBLIC_API_BASE_URL` when set — behind a reverse proxy `build_absolute_uri` yields the internal address, and the manifest then renders while not a single image loads.

The reader has three reading modes, and **each has its own mechanism**. Three were once shipped sharing one — OpenSeadragon — and none of the three was served by it, so they came back one at a time; `components/reader/` shares only `ReaderPageSurface` (an image at the measured width, with its text layer over it) and `usePagePreload` (when to ask for an image), never the behaviour. **Vertical scroll** stacks pages in a container that really scrolls, fitted to a comfortable reading width. **Horizontal strip** lays them side by side, each page whole — the more binding of the two dimensions decides, because fitting height alone made an A4 page wider than a phone held upright — and scroll-snap stops on a page, with room reserved at both ends so the first and last page can reach the centre too; its arithmetic lives in `stripLayout.ts` as pure functions, since jsdom measures nothing. **Two-page** holds one spread at a time and turns it: arrows at the mid-height extremes, keyboard, swipe, and draggable page corners that need a deliberate pull — a click there would turn the page while someone meant to move the view. Spreads pair the cover alone then (2,3), (4,5): pairing (1,2) puts the whole book out of step, and a reader who knows their pages sees it before you do. Below 768px the two-page mode shows one page, watched with `matchMedia` so rotating a phone actually changes it.

In scroll mode the reader is **a scroll**, not a viewport: pages stacked in a container that really scrolls, so wheel, trackpad, finger, arrow keys, scrollbar and Home all work without a line written for each. It was built on OpenSeadragon first, which was the wrong tool — OSD pans and zooms one image, so the wheel zoomed and advancing meant dragging the page; it drives Universal Viewer and Mirador, which show *one page at a time*, and that is its case, not ours. Removing it took the reader chunk from 367 kB to 15 kB. Zoom multiplies a reference width that is bounded **before** the multiplication, never after — written `min(100%, 52rem * zoom)` it capped at the container and did nothing past about 170 %. Each page measures its own width and asks the IIIF service for the smallest declared size that still covers it, so a phone never pays for a desktop's pixels. The route is lazily loaded and a bundle test keeps it out of the entry chunk. The word-layer stays ours: Universal Viewer shows OCR text only through a fork's plugin, and the CRKN accessibility study of Mirador 3 lists twelve defects, never covers text selection, and recommends downloading the searchable PDF — which the rights model forbids.

Every tile goes through the same `_authorized_page` as the text, and `PageAccessLog` keeps **one row per (session, page)**, enforced by a unique constraint. Writes that teach nothing are skipped: dozens of parallel tiles otherwise meant dozens of inserts plus a `last_seen_at` update each. Two tiles of an unread page still race — both read "no row", both write — and `full_clean()` turns the second into a `ValidationError`, which `get_or_create` does not catch; that 500 was invisible on SQLite, where the global lock serialised the writes.

**A page image cannot be fetched with `<img src>`**: that tag sends no `Authorization` header, so every page of a signed-in reader came back 403. The image is fetched like any other resource and handed to the browser as a `blob:` URL (`features/reader/pageImage.ts`); the query waits for `isHydrating` to clear, or it fires before the token is known. Unit tests could not see this — the test client authenticates the request — and it took a screenshot of a real browser to find it.

The image carries `private, no-store` where a **cover** carries `public, max-age` — a cover is a public thumbnail of a discoverable document, a page image is the content. Both log the access: an audit trail must not depend on which representation the client asked for. That is why `analytics` counts **distinct (session, page)** rather than `PageAccessLog` rows — two representations of one page are one page view, and the same dedup fixes an older defect where paging back inflated an institution's count.

### Ingestion pipeline

`ingest_document_file` registers the upload then enqueues a Celery chain:

```
ingest_source_document          split pages, extract the text layer, queue index records
  └─ per page, in order:        ocr_page → render_page_image → index_page
       └─ chord barrier      →  finalize_version
```

The barrier matters: `finalize_version` rebuilds the document index from page text, so it must run after OCR or recognised text never becomes searchable. Chords need a result backend — `CELERY_RESULT_BACKEND` defaults to the broker URL.

Domain logic lives in services, tasks are thin wrappers that take an id and reload the row, so any task can be replayed after a worker dies. `CELERY_TASK_ALWAYS_EAGER` is on outside production, so the suite and local development need no broker. `ingest_document_file(dispatch=False)` (exposed as `ingest_file --sync`) runs the same functions in the same order without Celery.

Storage is chosen by `DOCUMENT_STORAGE_BACKEND` (`filesystem` or `s3`) behind an unchanged `storage_key`; production refuses `filesystem`. Files are streamed, never fully read into memory. Page images are WebP derivatives of a private source, so they are private too and never appear in any catalog, search or reader payload — a regression test scans five responses for that.

Re-ingesting a populated version label raises `VersionAlreadyIngested`; `replace=True` clears the version, its assets and their stored objects in one transaction. `seed_demo` deliberately creates no pages — fabricated ones used to collide with real ingestion.

Search (`search_discovery/`) is a denormalized `DocumentSearchIndex` row per document rebuilt from indexable page text, scored in Python — the placeholder for Postgres FTS / Meilisearch. Unreadable pages keep a `[Page N …]` placeholder that is excluded from the index; indexing it made every scanned document match a search for "OCR requis".

### API v1 contract

All `/api/v1/` errors use one envelope — `{"error": {"code", "message", "field_errors"}}` — produced by `api/v1/errors.py` (`error_response` for explicit returns, `api_exception_handler` for DRF exceptions). Pagination is `StandardResultsSetPagination` (page size 20, max 50). Views are `APIView` subclasses annotated with `@extend_schema` including examples; `api/v1/tests/test_openapi_schema.py` guards the generated schema, so new endpoints need schema annotations. DRF default permission is `AllowAny` — every view states its own auth requirement.

### Staff API

`/api/staff/v1/` is a **separate namespace with its own OpenAPI schema**, generated from its own URL perimeter (`config/schema_staff.py`; the public one from `config/schema_public.py`). Scoping only the staff schema would leave the public one generating from the root urlconf and silently documenting internal endpoints — two tests assert both directions stay clean.

Every view inherits `StaffAPIView`, which applies the `has_back_office_access` floor. Inheriting `APIView` directly would fall back to the project default of `AllowAny`, making a forgotten permission publicly readable.

Visibility is scoped on the queryset (`api/staff/v1/scoping.py`): a content admin sees every publication state, a teacher only what they authored. A document out of scope returns **404, not 403** — answering "forbidden" would confirm a draft exists.

Rights enforce a separation of duties. The declaration serializer does not expose `authorization_status`, `authorization_date`, `reviewer_decision`, `rejection_reason` or `audit_reference`: the depositor declares, capped at `pending_review`, and only a content admin decides, supplying the signed contract's audit reference (or a rejection reason). Editing a declaration resets it to `pending_review`.

Two readiness gates, not one: `missing_deposit_requirements` (declaration complete) gates submission, `missing_publication_requirements` (declaration approved) gates publication. Collapsing them makes submission impossible, since approval happens after it.

Upload is the only multipart endpoint, a deliberate exception to the JSON-only public contract. Bounds are checked before storage is touched, and the file reaches `ingest_document_file` as a `TemporaryUploadedFile` above 2.5 MB rather than passing through memory.

### Back-office screens (`/gestion`)

The first lazily loaded area: `lazyRouteComponent` per route, and
`src/tests/staff-bundle.test.ts` asserts the reader entry chunk contains no
staff module **and** no `react-hook-form`. That test only trips on a reachable
usage — rolldown shakes an unused import away, which is why the mutation check
in it matters.

`RequireRole` mirrors `accounts.permissions.has_back_office_access` and refuses
with a message rather than a redirect: sending an already-authenticated reader
to `/connexion` loops. Both guards read the return target from the router
non-reactively — read reactively, it nested into itself
(`/connexion?next=/connexion?next=…`) until React gave up.

Staff forms use `react-hook-form` (D013), confined to `/gestion`.
`features/staff/applyApiErrors.ts` maps the error envelope onto fields via
`setError`, focuses only the first, routes an error on a field the form does
not own into the form-level message — `setError` on an unknown field is
silently swallowed — and never leaks a non-`ApiError` exception string.

Three parity guards live in `api/staff/v1/tests/`, all reading the frontend
files without running TypeScript, all failing rather than skipping when a path
is wrong:

- `test_frontend_enum_parity` — every `TextChoices` value appears in the
  matching TS list. A value missing there is simply unselectable, in silence.
- `test_frontend_type_parity` — every `types.ts` interface equals the real
  payload, in both directions. Screen tests use stubs; this is what stops a
  stub from lying.
- `test_openapi_staff` — the two schemas stay on their own URL perimeters.

`PublicationStatus` carries six values — the five of plan directeur §8.2 plus
rejected (D014). The three review states it used to carry duplicated gates
held better elsewhere: rights by `RightsAgreement.authorization_status`,
processing by `DocumentVersion.status` and `ProcessingJob`. Two
representations of one lock drift apart, and publication is what becomes
unpredictable. No gate was lost.

Enum values the screen does not know still degrade visibly: an unknown
publication status or completeness code renders raw rather than vanishing. A row with no
badge would read as "no state", and a checklist that drops a code would tell a
depositor nothing is missing while submission gets refused.

Upload bounds come from `/api/staff/v1/` — the server announces
`upload.max_bytes` and `accepted_mime_types`. A build-time copy would drift
from the real configuration. The screen checks them before opening a request
and still renders the server's 413/415, since a proxy can be stricter.

### Validation workflow

`/gestion/revues` is the only staff listing **not** scoped by authorship — a
reviewer must see what others deposited — so it is scoped by role instead.

Two refusals are structural, not conventional. A content admin who authored the
document cannot decide on it (`self_review_forbidden`): without that, the
separation of duties would hold only by luck of role assignment. And approving
a document whose rights are not approved is refused *at the endpoint*, naming
the blocking requirement — the service already refused, but a door that closes
without a visible reason reads as a fault.

`withdraw_document` and `archive_document` (in `operations/services.py`) delete
nothing: pages, version, index and rights survive, and only
`document_is_reader_accessible` changes its answer, because it tests for
`published`. Withdrawal is not a rights revocation — conflating them would make
republication demand a fresh approval it does not need. Both refuse an empty
reason and an absent actor: an anonymous, unmotivated disappearance is exactly
what an audit exists to prevent.

`SUBMITTABLE_STATES` is `draft | rejected | withdrawn`. Rejected belongs there
or a rejected document is stuck for life; withdrawn belongs there because
governance requires republication "through a new validation decision", and that
decision starts with a submission. This gap was found by walking the flow by
hand, not by a unit test — the endpoint tests each passed on their own.

The audit endpoint filters `metadata` through an allow-list
(`api/staff/v1/lifecycle.py`). That field is written by many services and
ingestion handles storage keys constantly; a privacy rule that depends on every
future writer being careful is not a rule. A test feeds it a deliberately
poisoned event.

`event_type` is a free string, not a `TextChoices`, so `auditLabels.ts` is not
covered by the enum-parity guard — which is exactly why an unknown type renders
raw instead of vanishing.

### Organizations and support

Organization scope is an **argument** to the predicate, never a filter applied
afterwards: every organization endpoint goes through one `_get_organization`
that asks `administers_organization(user, organization)`. A divergent filter
would expose one institution's members to another while the nominal case kept
working, which is what makes that defect invisible. Out of scope, an
organization is **404, not 403**.

No payload or screen names who read what. Not deferred — excluded. The usage
report is built from `DailyUsageAggregate`, never `PageAccessLog`, and a test
walks the report's keys against an exact per-user denylist. Substring matching
was tried and rejected: it flagged `reader_session_count`, a legitimate
aggregate, and a false test pushes toward weakening the rule.

`SupportTicket.category` splits support, document reports and withdrawal
requests. A withdrawal *request* withdraws nothing — it opens a high-priority
ticket a moderator acts on, so contract-bound categories keep the protection
`can_withdraw_document` gives them, and the screen says so in as many words.

`seed_demo` is **reparative**, not merely idempotent: it re-applies demo
passwords and membership states on every run. `get_or_create` never writes to an
existing row, so a demo that suspended a member left the dataset broken with no
way back. Beware `manage.py seed_demo | head`: SIGPIPE kills it mid-transaction
and nothing is committed.

### Public journey

The catalogue list endpoint takes **no filter at all** — no domain, no language, no year, no ordering — so the catalogue's filter panel submits to `/recherche`, which does support them, and the document page reaches its domain neighbours the same way. Search results carry `matched_in`, the fields that actually answered: the scale notes a title match a thousand times higher than a word met in passing (1075 against 5), and without it both rendered identically, so a search for "droit" looked like it returned the whole catalogue. The fields are named where the scale is applied, never decomposed on the screen — two copies of one scale drift apart.

A document page answers in the order the questions are asked: what it is (the academic nature — course, thesis, dissertation, exam paper — which travelled in the payload for months without ever being displayed), who wrote it and where, what it holds, **what the access allows in plain words** (`institution_only` teaches a student nothing), how to cite it, and what else shares its domain. The two statements that bind the platform — what the access allows, and the reference to copy — are pure functions with their own tests, and the reference **omits** what is missing rather than fabricating it: an "s.d." or an "anonyme" gets copied into a bibliography and becomes true there.

Displayed French carries its accents, and `src/tests/accents.test.ts` enforces it: it reads the text of JSX nodes and the props that reach the screen, never a URL segment or a class name (`/bibliotheque` is an address, not a word). A fix had already claimed to restore them; proof-reading by eye caught part and left about thirty strings, including the pagination bar that shows on every listing. A spelling mistake breaks nothing and no test falls — which is exactly why it survives.

### Frontend

TanStack Router routes declared centrally in `src/router.tsx` (French URL segments: `/connexion`, `/recherche`, `/lecture/...`, `/bibliotheque`). Layers: `src/api/` (typed fetch wrappers over `apiRequest`, which unwraps the error envelope into `ApiError`), `src/features/<domain>/hooks.ts` (TanStack Query hooks), `src/routes/` (pages), `src/components/` (presentational). Auth state lives in `src/auth/` — `AuthProvider.tsx` holds the provider, `authContext.ts` the context and `useAuth.ts` the hook. They are three files on purpose: a module exporting both a component and a value breaks hot-reload granularity, and `npm run lint` is silent so a new mix shows up immediately. JWT access/refresh live in `localStorage` via `tokenStore`; a 401 dispatches `UNAUTHORIZED_EVENT` so the provider can clear the session, and `guards.tsx` redirects to `/connexion?next=...`. Import alias `@/` → `src/`.

## Conventions and invariants

- A root `conftest.py` renders pages small for the whole suite: tiling one page at the production 300 dpi costs ~1.7 s and 54 objects, which pushed the suite past forty minutes to verify access and logging rules that do not depend on resolution. It sets `settings`, never an environment variable — `config/tests/test_env.py` checks the production default by importing settings in a subprocess, where an environment variable would propagate.
- Tests live in `backend/<app>/tests/` and `frontend/src/**/tests/`; `pytest.ini` lists `testpaths` explicitly — a new app's test directory must be added there (and to `pyproject.toml`'s matching list) or its tests silently never run.
- Cover success, denial, idempotency, privacy and boundary conditions — especially for reader access, billing and analytics. Prefer real model/service behaviour over mocks.
- `select_for_update()` beside `select_related()` needs `of=("self",)`: PostgreSQL refuses `FOR UPDATE` as soon as the query has an outer join on a nullable key, and each optional relation adds one. `of` also says what was meant — lock the row about to change, not the rows joined for display.
- Payments and webhooks must be idempotent (`idempotency_key` with a terms check that rejects reuse under different terms — see `billing.services.create_payment_transaction`).
- Sensitive admin/access decisions go through `operations.services.record_audit_event`.
- Institutional analytics aggregate to `DailyUsageAggregate`; reports must not leak per-user reading data.
- OCR needs `tesseract-ocr` and `tesseract-ocr-fra`; without them those tests skip and the pipeline keeps going with placeholders.
- Config comes from env vars only, documented in `backend/.env.example`. `config/env.py` hard-fails production on unsafe settings (debug on, default secret key, missing allowed hosts, insecure cookies) — don't loosen those checks.
- Never commit secrets, raw documents, or production database URLs.
- Commits use conventional prefixes (`feat:`, `fix:`, `docs:`, `test:`, `ci:`) with short imperative subjects.

## Docs map

- `docs/technical/00-subsystem-plan-index.md` — stack direction, shared domain concepts, cross-cutting requirements.
- `docs/superpowers/plans/` and `docs/superpowers/specs/` — per-subsystem design and implementation plans, dated; read the matching one before reworking a subsystem.
- `docs/operations/` — backup/restore, incident response, deployment checklist.
- `docs/product/`, `docs/business/` — baseline, roles, rights governance, commercial offers.
- `AGENTS.md` — the same conventions in short form (keep the two consistent when either changes).
