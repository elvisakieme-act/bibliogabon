# BiblioGABON Back-Office Deposit Screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The first screens of the production back-office, so a teacher deposits a document without a terminal and a moderator sees what is waiting.

**Architecture:** A lazily loaded `/gestion` area inside the existing React application, consuming the staff API through the existing `apiRequest`, with one addition for multipart upload. Deposit is a detail page with progressive sections rather than one long form, driven by the `missing_for_submission` checklist the API already returns.

**Tech Stack:** React 19, TypeScript, Vite, TanStack Router, TanStack Query, Tailwind, Vitest, Testing Library.

Slice 2 of 4 of `docs/superpowers/specs/2026-09-27-bibliogabon-back-office-design.md`.

## Global Constraints

- A reader must never download the staff bundle. The area is lazily loaded and a test asserts it.
- No screen renders a storage key, a `.pdf` path or a URL to a source file — the API rule, enforced again where a template could reintroduce it.
- The UI hides what a role cannot do, but hiding is a courtesy: every screen must render a server refusal rather than assume it cannot happen.
- Staff forms use `react-hook-form` (D013), confined to `/gestion`. Server `field_errors` reach inputs through `setError`; per-field accessibility comes from the shared `components/ui/FieldErrors`. The reader's auth forms are not migrated.
- The reader routes, their components and their tests are untouched.
- Do not build the review workflow, organizations, support, bulk deposit or notifications.
- Use TDD: write the failing test, run it red for the expected reason, implement, run green, then commit.

---

## File Structure

```text
frontend/src/
  api/
    staff.ts                   # typed calls against /api/staff/v1/
    upload.ts                  # apiUpload, the only XMLHttpRequest in the codebase
    types.ts                   # StaffDocument and friends
  auth/
    guards.tsx                 # RequireRole alongside RequireAuth
  features/staff/
    hooks.ts                   # queries and mutations
  components/staff/
    DocumentStateBadge.tsx
    CompletenessChecklist.tsx
    SourceUpload.tsx
    IngestionStatus.tsx
  routes/gestion/
    GestionLayout.tsx
    DashboardPage.tsx
    DocumentsPage.tsx
    DocumentCreatePage.tsx
    DocumentDetailPage.tsx
  features/staff/applyApiErrors.ts
  tests/
    staff-guard.test.tsx
    staff-bundle.test.ts
    staff-deposit.test.tsx
    api-errors-to-form.test.tsx
    staff-documents.test.tsx
    staff-ingestion.test.tsx
```

---

### Task 1: Role Guard And Lazy Area

**Files:**
- Modify: `frontend/src/auth/guards.tsx`, `frontend/src/router.tsx`
- Create: `frontend/src/routes/gestion/GestionLayout.tsx`, `.../DashboardPage.tsx`
- Create: `frontend/src/tests/staff-guard.test.tsx`, `frontend/src/tests/staff-bundle.test.ts`

**Interfaces:**
- Produces `RequireRole`.
- Produces the `/gestion` route tree, lazily loaded.

- [x] Write failing tests: `RequireRole` renders its children for a content admin and a teacher, refuses an individual account with a plain message rather than a redirect, and sends an anonymous visitor to `/connexion` with a return target.
- [x] Write a failing test asserting the built entry chunk contains no staff module. Run `vite build` and inspect the manifest — without this, the split regresses silently the first time someone adds a static import to the staff area.
- [x] Implement `RequireRole` reading `account_type` from the hydrated user.
- [x] Register the `/gestion` routes with lazily loaded components.
- [x] Run `npm run test` and `npm run build`.
- [x] Commit `feat: add the lazily loaded back-office area`.

---

### Task 2: Staff API Client

**Files:**
- Create: `frontend/src/api/staff.ts`, `frontend/src/api/upload.ts`
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/api/tests/staff.test.ts`

**Interfaces:**
- Produces typed calls for documents, authors, rights, source and ingestion.
- Produces `apiUpload(path, file, { token, onProgress, signal })`.

- [x] Write failing tests: each call hits the right `/api/staff/v1/` path with the bearer token; an error envelope becomes an `ApiError` carrying `field_errors`; `apiUpload` sends `FormData` and **does not** set `Content-Type`, since the browser must write the multipart boundary.
- [x] Write a failing test that `apiUpload` reports progress and rejects with `ApiError` on a 413.
- [x] Implement, reusing `apiRequest` for everything but upload.
- [x] Implement `apiUpload` on `XMLHttpRequest`, with a comment saying why: `fetch` cannot observe upload progress in a browser, and this is the one place the product needs it.
- [x] Run `npm run test`.
- [x] Commit `feat: add the staff API client`.

---

### Task 3: Server Refusals Onto Form Fields

Installs `react-hook-form` (D013) and bridges it to the API error envelope.
`components/ui/FieldErrors` already exists and already carries the
accessibility contract (`fieldErrorId`, `fieldErrorProps`); this task adds the
mapping, not a second error component.

**Files:**
- Create: `frontend/src/features/staff/applyApiErrors.ts`
- Create: `frontend/src/tests/api-errors-to-form.test.tsx`
- Modify: `frontend/package.json` (add `react-hook-form`)

**Interfaces:**
- Produces `applyApiErrors(error, setError) => string`, returning the form-level message.

- [x] Write failing tests: an `ApiError` with `field_errors` calls `setError` for each named field; a field the form does not own does not vanish silently but joins the form-level message; an error with only a message becomes a form-level message; a non-`ApiError` becomes a generic message rather than leaking an exception string to the user; submitting again clears the previous refusal.
- [x] Write a failing test on a throwaway form: after a refusal, the offending input carries `aria-invalid` and an `aria-describedby` that resolves to the visible message, and focus moves to the first field in error.
- [x] Install `react-hook-form`, implement the mapping.
- [x] Run `npm run test` and `npm run format:check`.
- [x] Commit `feat: map API field errors onto form inputs`.

---

### Task 4: Catalogue List

**Files:**
- Create: `frontend/src/features/staff/hooks.ts`, `frontend/src/routes/gestion/DocumentsPage.tsx`, `frontend/src/components/staff/DocumentStateBadge.tsx`
- Create: `frontend/src/tests/staff-documents.test.tsx`

**Interfaces:**
- Produces `/gestion/documents`.

- [ ] Write failing tests: the list renders title, state badge, domain and type; filters by state, domain, type and title fragment drive the query; pagination uses the API envelope; loading, empty and error states each render; a server refusal renders as a refusal rather than an empty list.
- [ ] Write a failing test asserting no rendered row contains a storage key, a `.pdf` path or a `://`.
- [ ] Implement the page and its query hooks.
- [ ] Run `npm run test`.
- [ ] Commit `feat: add the back-office document list`.

---

### Task 5: Draft Creation And Metadata

**Files:**
- Create: `frontend/src/routes/gestion/DocumentCreatePage.tsx`, `.../DocumentDetailPage.tsx`, `frontend/src/components/staff/CompletenessChecklist.tsx`
- Create: `frontend/src/tests/staff-deposit.test.tsx`

**Interfaces:**
- Produces `/gestion/documents/nouveau` and `/gestion/documents/:id`.

- [ ] Write failing tests: creating a draft with the minimum fields navigates to its detail page; a server `field_errors` refusal lands on the right inputs; the metadata section saves and reflects the response.
- [ ] Write failing tests for the checklist: it renders each entry of `missing_for_submission` in French, the submit action is disabled while it is non-empty, and it disappears when the list empties.
- [ ] Implement the pages, keeping each section a short independent form.
- [ ] Translate the completeness codes in one place, so a new server code surfaces as an untranslated code rather than silently vanishing from the checklist.
- [ ] Run `npm run test`.
- [ ] Commit `feat: add draft creation and metadata editing`.

---

### Task 6: Authors And Rights Sections

**Files:**
- Modify: `frontend/src/routes/gestion/DocumentDetailPage.tsx`
- Modify: `frontend/src/tests/staff-deposit.test.tsx`

- [ ] Write failing tests: attaching an author appends it with its role; detaching removes it; the rights form saves a declaration and shows its status as pending review.
- [ ] Write a failing test asserting the rights form exposes **no** approval control: approval belongs to the moderator, and a disabled button would still tell the depositor to ask for one.
- [ ] Implement both sections.
- [ ] Run `npm run test`.
- [ ] Commit `feat: add author and rights sections to the deposit screen`.

---

### Task 7: Upload And Ingestion Feedback

**Files:**
- Create: `frontend/src/components/staff/SourceUpload.tsx`, `.../IngestionStatus.tsx`
- Create: `frontend/src/tests/staff-ingestion.test.tsx`

- [ ] Write failing tests: choosing a file over the configured limit is refused before any request; the server's 413 and 415 refusals render legibly; a successful upload shows the version and page count.
- [ ] Write failing tests for polling: it runs while the state is `in_progress`, stops on `ready`, stops on `failed`, and a failed job shows its reason with a re-upload action. This is the only place a user waits on a worker, so an endless spinner is a defect, not a cosmetic issue.
- [ ] Implement both components on `apiUpload` and a polled query.
- [ ] Run `npm run test`.
- [ ] Commit `feat: add source upload and ingestion feedback`.

---

### Task 8: Verification And Documentation

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `frontend/README.md`

- [ ] Re-assert the bundle split after seven tasks of additions: the reader entry chunk still contains no staff module.
- [ ] Walk the flow by hand against the running backend: create, metadata, author, rights, upload, watch ingestion, submit. Record what the screens actually did, not what they should do.
- [ ] Document the area in `CLAUDE.md` and the deposit path for a contributor in `README.md`.
- [ ] Run `npm run lint`, `npm run test`, `npm run build`, and the backend suite.
- [ ] Commit `docs: document the back-office deposit screens`.

---

## Self-Review Checklist

- [ ] The reader entry chunk contains no staff module.
- [ ] `RequireRole` refuses a reader and admits staff; an anonymous visitor is sent to login with a return target.
- [ ] No rendered screen contains a storage key, a `.pdf` path or a source URL.
- [ ] Every form renders server `field_errors` on the right input and a form-level message otherwise.
- [ ] A non-`ApiError` failure shows a human message, never an exception string.
- [ ] The checklist reflects `missing_for_submission` and gates the submit action.
- [ ] An unknown completeness code surfaces visibly rather than vanishing.
- [ ] The rights form offers no approval control at all.
- [ ] Upload refuses an oversized file client-side and renders the server refusal too.
- [ ] Ingestion polling stops on both terminal states, and a failure shows its reason.
- [ ] Reader routes, components and tests are unchanged.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-27-bibliogabon-back-office-deposit-screens.md`.

Recommended execution: sequential TDD. Tasks 2 and 3 gate 4 to 7. Task 7 carries the most risk — upload and polling are the two places where the browser, the broker and the storage all have to agree.

After this slice a teacher deposits without a terminal. Slice 3 adds the review workflow, and Phase 1's third line closes with it.
