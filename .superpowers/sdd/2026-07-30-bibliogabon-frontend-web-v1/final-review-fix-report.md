# Final Review Fix Report

Date: 2026-07-31

Status: `DONE_WITH_CONCERNS`

Implementation commit:
`c06fbbda2f3656c1ed21ac09f1aa893b9e31e847`

## Scope

- Added narrow, dependency-free Django CORS handling and allowed/disallowed
  origin and preflight coverage.
- Persisted authenticated reading progress, restored resume pages, and added
  count-backed incremental library pagination.
- Corrected catalog access values, clamped URL pagination, normalized API base
  URLs, and centralized token-authenticated 401 session clearing.
- Added an actionable document-detail login CTA with a return target and a
  route-level not-found test.
- Restored the maquette Home composition, responsive sticky Catalog filters,
  existing hero media, Ken Burns and Reveal primitives, trust cues, and domain
  bento content.
- Self-hosted Fraunces and Space Grotesk with `font-display: swap`, source
  notes, and the SIL Open Font License 1.1.

## RED Evidence

Recovery began from a broad uncommitted patch, so the prior implementer's
original RED command output for the inherited behavior tests was unavailable.
The fix-base source at `7c2af1b` provides the pre-fix behavior for those tests:

- CORS tests: no `config.cors` middleware or response headers existed.
- Reader/library tests: no progress PATCH occurred and resume links opened page
  1; only first-page results and result lengths were used.
- Catalog tests: `institutional` and `paid` were offered instead of the five API
  values; Catalog and Search parsed URL pagination without bounds.
- Auth/client tests: token-authenticated 401 responses emitted no global event
  and did not centrally clear the session.
- Document detail test: authentication-required access rendered a passive
  `span`, not a login link with a return target.
- Client/not-found tests: configured API trailing slashes were not normalized
  and no route-level unknown-URL assertion existed.

Actual recovery RED runs:

- Focused frontend run: `1 failed, 39 passed`; Home failed because
  `Reveal` called unavailable `window.matchMedia`.
- First production build: failed with `TS2493` because three fetch mocks were
  inferred as zero-argument tuples before their request URLs were inspected.

The added Catalog-route clamping assertion was GREEN on its first run because
the shared clamping implementation was already present in the inherited patch.

## GREEN Evidence

- Focused frontend behavior suite: `6` files, `40` tests passed.
- Focused Catalog route suite after added coverage: `18` tests passed.
- Focused backend CORS suite: `4` tests passed.
- `npm run lint`: exit `0`, `0` errors, `5` warnings.
- `npm run test`: `7` files, `47` tests passed.
- `npm run build`: TypeScript and Vite production build passed; `1884` modules
  transformed.
- `D:\bibliogabon\backend\.venv\Scripts\python.exe -m pytest config/tests
  api/v1/tests -q`: `87` tests passed.
- `git diff --cached --check`: passed before the implementation commit.
- Hero asset SHA-256 matches the existing maquette asset.

## Concerns

- Lint still reports five pre-existing warnings: four Fast Refresh export
  warnings and one `ProfilPage` hook-dependency warning.
- The in-app browser runtime exposed no browser instance, so visual validation
  was limited to source review, direct hero-asset inspection, tests, and the
  production build rather than responsive browser screenshots.
