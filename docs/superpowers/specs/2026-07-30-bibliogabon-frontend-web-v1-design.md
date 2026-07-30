# BiblioGABON Frontend Web V1 Design

## Purpose

This slice defines the first real BiblioGABON web frontend. It turns the completed `/api/v1/` backend into a usable reader-facing product while preserving the visual identity of `maquette-bibliogabon/`.

The frontend must not become a generic SaaS shell or a plain catalog. The maquette is the UI/UX source of truth for visual DNA; the new frontend is a clean implementation that rebuilds routing, state, authentication, and data access around the real API.

## Product Scope

Frontend Web V1 focuses on the reader experience:

- public discovery home;
- document catalog and domain browsing;
- search;
- document detail;
- secure reader;
- individual registration and JWT login;
- personal library with favorites and reading progress;
- lightweight profile view.

Institution admin, staff workflows, ingestion, content review, billing checkout, teacher/contributor spaces, and long institutional marketing pages remain out of scope for this slice.

## Source References

- `docs/product/03-frontend-maquette-ui-audit.md`
- `docs/superpowers/specs/2026-07-29-bibliogabon-api-v1-contract-design.md`
- `maquette-bibliogabon/`

## Technical Approach

Create a new `frontend/` application. Keep `maquette-bibliogabon/` untouched as a reference project.

Use:

- React with TypeScript;
- Vite for build and development;
- TanStack Router for route structure;
- TanStack Query for API loading, caching, and invalidation;
- Tailwind CSS and Radix/shadcn-style primitives where useful;
- lucide-react icons, matching the maquette;
- a small typed API client for `/api/v1/`.

Use npm scripts for development and verification. The frontend must read the API base URL from `VITE_API_BASE_URL`, defaulting to the local Django server during development.

## Project Structure

```text
frontend/
  src/
    api/
      client.ts
      auth.ts
      catalog.ts
      reader.ts
      library.ts
      types.ts
    auth/
      AuthProvider.tsx
      tokenStore.ts
      guards.tsx
    components/
      brand/
      layout/
      catalog/
      reader/
      ui/
    features/
      catalog/
      reader/
      library/
    routes/
    styles/
      globals.css
    main.tsx
    router.tsx
```

Keep feature logic close to the feature. Shared visual primitives live in `components/`; API contracts live in `api/types.ts`.

## Visual System Requirements

Preserve these maquette elements:

- the BiblioGABON logo asset and wordmark behavior;
- navy, navy-deep, green, gold, soft academic surfaces;
- Fraunces for display typography and Space Grotesk for body/interface typography;
- `gabon-stripe`, `gabon-rule`, `container-editorial`;
- sticky glass navbar on scroll;
- card hover lift, image scale, editorial shadows, bottom gold hover rule;
- rounded `2xl` card language where inherited from the maquette;
- Reveal-on-scroll, Ken Burns hero fallback, typewriter wordmark, count-in stats;
- `prefers-reduced-motion` behavior and visible gold focus rings.

Any visual simplification must be justified by mobile performance, accessibility, or API-driven UX clarity. The default is preservation.

## Routes

```text
/                      Discovery home
/catalogue             Public document catalog
/recherche             Search results
/domaines              Domain index
/domaines/:slug        Domain-filtered catalog
/documents/:id         Document detail
/lecture/:documentId   Secure reader
/connexion             JWT login
/inscription           Individual registration
/bibliotheque          Favorites and reading progress
/profil                Current user profile
```

Routes removed from V1 as primary routes: `/livres`, `/articles`, `/cours`, `/examens`, `/theses`, `/enseignants`, `/vision`, `/apropos`, `/contact`. Their visual ideas can feed later slices.

## API Integration

All runtime data comes from `/api/v1/`.

Use these endpoint groups:

- Auth: register, token, refresh, logout.
- Current user: `GET/PATCH /api/v1/me/`.
- Catalog: documents, document detail, domains, authors.
- Search: `GET /api/v1/search/`.
- Reader: create session, fetch page, close session.
- Library: favorites and reading progress.

The client must send JSON only. It must handle the backend error envelope:

```json
{
  "error": {
    "code": "entitlement_required",
    "message": "An active read entitlement is required.",
    "field_errors": {}
  }
}
```

## Authentication And Session

Store JWT tokens in a dedicated token store abstraction, not scattered localStorage calls. The initial implementation may use localStorage, but all access must go through `tokenStore`.

Required behavior:

- login stores access and refresh tokens;
- logout calls the API and clears local tokens even if the API request fails;
- authenticated requests attach `Authorization: Bearer <access>`;
- `GET /api/v1/me/` hydrates the current user;
- 401 responses move the UI to an unauthenticated state;
- protected routes redirect to `/connexion` with a return target.

Registration creates only individual accounts. Do not expose teacher, staff, or institution role selection in V1.

## Page Designs

### Home

Use the maquette's rich home visual language: strong hero/media area, trust/impact cues, domain bento, featured documents, and editorial spacing. Replace mock claims and counts with API-backed values or conservative copy. Search must be immediately visible.

### Catalog And Search

Preserve the maquette's two-column desktop browser with sticky filter panel and responsive card grid. Rebuild filters around API query parameters:

- query;
- domain;
- language;
- access model;
- publication year;
- page and page size.

Use skeletons, empty states, pagination controls, and normalized API error displays.

### Document Detail

Preserve the cover-left/content-right hero, metadata chips, domain badge, summary, and access panel. Adapt CTA logic:

- free/open-access: read now;
- restricted anonymous: sign in to read;
- restricted authenticated without grant: access required;
- private/unpublished/not found: not found state.

Do not render download buttons in V1.

### Reader

The reader opens through the reader session API. It must show:

- document title and page position;
- previous/next controls;
- page content from the API response;
- session expiry or access-error states;
- return-to-document action.

For restricted documents, the frontend relies on the backend for entitlement checks and displays 401/403 responses clearly.

### Library And Profile

`/bibliotheque` shows favorites and reading progress only. It must not expose detailed page access history. The visual style can reuse the maquette dashboard cards, but labels become product-accurate: favorites, resume reading, recent progress.

`/profil` exposes only current user fields supported by `/api/v1/me/`.

## States And Error Handling

Every API-backed screen must define:

- loading skeleton;
- empty state;
- normalized API error state;
- unauthenticated state;
- forbidden/entitlement-required state;
- not-found state;
- network-unavailable state.

Keep empty and error states visually aligned with the maquette's `EmptyState` pattern.

## Assets

Migrate only approved visual assets:

- logo and favicons;
- selected hero imagery;
- domain cover imagery where useful;
- generic document cover fallback patterns.

Do not migrate demo EPUB files, raw document downloads, fake account data, or mock document datasets as runtime data.

## Security And Privacy

- Never expose raw files, storage keys, signed URLs, OCR full text, payment metadata, or detailed reading logs.
- Do not infer hidden document existence from API errors; display a generic not-found state when the API returns 404.
- Do not store passwords.
- Do not log tokens or raw API request bodies.
- Do not add download/offline behavior until a safe backend contract exists.

## Testing

Use frontend tests sized to risk:

- API client tests for auth headers, JSON-only requests, error envelope parsing;
- route/component tests for catalog, document detail, reader, and library states;
- auth flow tests for login/logout/register and protected route redirect;
- reader tests for anonymous free read and restricted access states;
- visual regression or screenshot checks for the core maquette-derived components when the tooling is available.

Build verification must include:

```powershell
npm run lint
npm run build
```

If tests are added:

```powershell
npm test
```

## Out Of Scope

- Payment checkout UI.
- Institution dashboards.
- Staff or content-admin frontend.
- Contributor/teacher profile product flows.
- Public download, offline mode, watermarking, or DRM controls.
- Native mobile application.
- Full marketing site rebuild.

## Acceptance Criteria

- The app is created in `frontend/`, not by mutating `maquette-bibliogabon/`.
- Visual identity matches the maquette audit.
- Runtime data comes from `/api/v1/`, not mock files.
- Core reader flow works for anonymous free documents.
- Restricted document states are handled without exposing private data.
- JWT auth and current-user hydration work.
- Catalog/search/list pages use pagination and loading/error/empty states.
- No download button or raw document link appears in V1.
- `npm run build` succeeds.
