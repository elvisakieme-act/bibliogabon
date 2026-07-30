# Frontend Maquette UI/UX Audit

## Purpose

This audit defines what the future BiblioGABON web frontend must preserve from `maquette-bibliogabon/`, and what must be removed or rebuilt to match the real API V1 product.

The maquette remains the visual source of truth. The new product frontend should not drift into a generic SaaS, generic library, or plain admin interface.

## Audit Scope

Reviewed areas:

- `maquette-bibliogabon/src/styles.css`
- shared components under `src/components/brand/` and `src/components/site/`
- key routes: home, catalog-like pages, domain pages, document detail, reader, login, registration, dashboard
- mock data under `src/data/`
- public assets under `public/`

The maquette contains 21 route files, 36 document cover assets, 17 domain cover assets, 12 hero assets, logo/favicons, and demo EPUB files.

## Preserve As Visual DNA

Keep these design foundations:

- Logo: book, Gabon outline, pixels, blue/green/yellow identity.
- Palette: navy, navy-deep, green, gold, soft academic surfaces.
- Typography: editorial serif display style plus geometric sans body style.
- National visual marker: `gabon-stripe` and `gabon-rule`.
- Layout rhythm: `container-editorial`, generous editorial spacing, restrained page width.
- Shadows: `shadow-editorial` and `shadow-editorial-lg`.
- Motion: reveal-on-scroll, hover lift, card shadow transition, image scale on hover, Ken Burns hero fallback, count-in stats, typewriter wordmark.
- Accessibility behavior: `prefers-reduced-motion` support and visible gold focus rings.

These effects must be carried into `frontend/` unless a concrete usability issue appears during implementation.

## Preserve And Adapt

### Layout Components

- `Logo`: preserve exactly as brand anchor; adapt asset import path.
- `SiteLayout`: preserve page shell idea; rebuild for the real route tree.
- `Navbar`: preserve sticky glass effect, top Gabon stripe, inline search, mobile menu, auth CTA area. Adapt menu items to V1 routes: Accueil, Catalogue, Domaines, Recherche, Bibliothèque, Connexion/Inscription.
- `Footer`: preserve visual style and national tone. Reduce links to V1-safe links and legal placeholders.
- `PageHeader`: preserve hero-card layout, breadcrumb, domain accent, image fallback.

### Catalog Components

- `DocumentCard`: preserve cover treatment, badges, hover lift, domain color logic, language chip, bottom gold hover rule. Adapt fields from API metadata and access block.
- `DocumentCover`: preserve fallback chain concept. In V1, use approved API cover URL when available; otherwise generate domain/type fallback locally.
- `DomainBadge`: preserve.
- `CatalogueBrowser`: preserve two-column desktop layout and sticky filter panel. Rebuild state around API query params, server pagination, loading states, and URL search params.
- `EmptyState`: preserve.
- `Reveal`: preserve, including reduced-motion handling.

### Pages And Flows

- Home: preserve rich visual language, hero/media treatment, stats band, domain bento, featured document sections. Replace mock counts with API-backed or conservative static product copy.
- Domain index/detail: preserve card grid, numbering, accent colors, and domain-focused browsing. Adapt to API domains endpoint.
- Document detail: preserve cover-left/content-right hero, metadata chips, access panel, similar documents section style. Remove download and teacher-profile dependency.
- Reader: preserve sober reading surface and document toolbar direction. Rebuild around reader sessions and page navigation.
- Login/Register: preserve split-screen login style and centered registration card style. Replace demo accounts and role selector with real individual account flow.
- Dashboard: preserve card/stat section language, but rebuild as `/bibliotheque` with favorites and reading progress only.

## Remove From V1 Product

Remove or do not migrate:

- `src/data/*` as runtime source of truth.
- demo accounts and plaintext demo passwords.
- direct EPUB/public document downloads from `public/docs/`.
- generated HTML download logic.
- teacher/contributor profile routes and teacher role registration.
- standalone category routes as primary product routes: `/livres`, `/articles`, `/cours`, `/examens`, `/theses`. Replace with `/catalogue` filters.
- long vitrine routes as primary V1 scope: `/vision`, `/apropos`, `/contact`, `/enseignants`.
- source-platform marketing blocks such as FUN-MOOC/MIT/OpenStax as product sections unless later validated by content strategy.
- claims such as "100 % gratuit" when the product has free, restricted, institutional, sponsored, and subscription access models.

## Keep For Later

Keep as backlog inspiration, not V1 implementation:

- Vision/storytelling sections.
- Contributor/teacher cards.
- Institution trust strip.
- Source-libre section.
- Social footer links.
- Hero pages for articles/cours/livres/examens/theses.
- Demo EPUB assets, only as local design references.

## Required V1 Route Mapping

The new `frontend/` should implement:

- `/`: discovery home using maquette visual language.
- `/catalogue`: document catalog with filters and pagination.
- `/recherche`: search results.
- `/domaines`: domain index.
- `/domaines/:slug`: domain-filtered catalog.
- `/documents/:id`: document detail.
- `/lecture/:documentId`: secure reader.
- `/connexion`: JWT login.
- `/inscription`: individual public registration.
- `/bibliotheque`: favorites and reading progress.
- `/profil`: small account profile page.

## API Alignment Rules

- All real data must come from `/api/v1/`.
- Use JWT access/refresh tokens; no fake local demo identity.
- Free documents can open the reader anonymously.
- Restricted documents show login or entitlement-required states.
- The frontend must never expose or link raw files, storage keys, signed URLs, OCR full text, payment metadata, or detailed reading logs.
- No download button in V1 unless a future API explicitly provides a safe public contract for it.

## Design Risks To Correct While Preserving Style

- Several source files display mojibake text encoding artifacts. The real frontend must use clean UTF-8 French text.
- Some hero images are large; preserve the visual treatment but optimize loading and avoid heavy autoplay on mobile.
- The maquette’s route count is larger than V1. Keep the visual system, not the full navigation.
- The maquette’s rounded `2xl` cards are part of its identity. Preserve them consistently rather than mixing unrelated radii.
- The design should remain academic/editorial, not marketing-only. Dense catalog and reader workflows must stay efficient.

## Implementation Principle

Create a clean `frontend/` application. Migrate visual patterns selectively from `maquette-bibliogabon/`, but rebuild product logic, data access, routing, and auth around the real API V1 contract.

