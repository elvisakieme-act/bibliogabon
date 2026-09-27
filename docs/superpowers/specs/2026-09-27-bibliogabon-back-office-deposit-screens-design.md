# BiblioGABON Back-Office Deposit Screens Design

## Purpose

Slice 2 of `docs/superpowers/specs/2026-09-27-bibliogabon-back-office-design.md`: the first screens of the production back-office, covering deposit and catalogue. After this slice a teacher deposits a document without a terminal, and a moderator sees what is waiting.

It does not build the review workflow, organization management or support. Those are slices 3 and 4.

## Why This Slice Exists

Slice 1 delivered the staff API. Nothing consumes it. The shell command is still the only way anyone actually deposits a document, so the content strategy — teacher ambassadors supplying the initial catalogue — remains blocked on developer availability.

## Product Rules

The back-office is a staff surface inside the reader application, not a second application. One session, one API client, one design system, one build.

A reader must never download it. The area is a separate chunk, loaded only when a staff route is entered.

The screens show what the API returns and nothing more. No storage key, no source download link, no page image — the same rule as the API, enforced again at the rendering layer because a template is where such a field slips back in.

Authority is the server's answer, never the client's guess. The UI hides what a role cannot do, but hiding is a courtesy: every action is refused server-side regardless, and the screens must render a server refusal rather than assume it cannot happen.

## Architecture

### Routes

Under `/gestion`, consistent with the French route names already in use:

```
/gestion                      dashboard: what is waiting, by state
/gestion/documents            catalogue with real filters
/gestion/documents/nouveau    create a draft
/gestion/documents/:id        detail: metadata, authors, rights, source, ingestion
```

`RequireRole` guards the area, mirroring the existing `RequireAuth`. An authenticated reader landing on `/gestion` gets a plain refusal, not a redirect loop.

### Lazy loading

The staff area is the first lazily loaded part of the application. TanStack Router loads the route component on demand so the reader bundle does not grow. A test asserts the staff modules are absent from the entry chunk — otherwise the split silently regresses the first time someone adds a static import.

### Staff API client

`src/api/staff/` reusing the existing `apiRequest`: the host is the same, only the paths differ, so a second client would duplicate the error-envelope handling and the token plumbing.

One genuine addition: `apiUpload`, because `apiRequest` JSON-stringifies its body. Upload sends `FormData`, must not set `Content-Type` by hand — the browser writes the multipart boundary — and should report progress, which `fetch` cannot do for uploads. `XMLHttpRequest` remains the only way to observe upload progress in a browser; that is why it appears in a codebase that otherwise uses `fetch`, and the code should say so.

### Forms

Hand-rolled with `useState`, matching the existing auth pages. No form library: it would be a new dependency for one area, and the pattern already in the codebase works at this size.

The reusable part is not state management but error mapping. `field_errors` from the API envelope must land on the right input, so a small `useFieldErrors` helper turns one server refusal into per-field messages plus a form-level message. That is specific to our envelope and is what a library would not give us.

Deposit is a detail page with progressive sections, not one long form. Creating a draft asks for the minimum; the document page then fills metadata, authors, rights and the file in separate small forms. This keeps each form short, lets a teacher save early, and lines up with what the API already returns: `missing_for_submission` drives a visible checklist, so the screen never has to restate the completeness rules.

### Ingestion feedback

`GET .../ingestion/` is polled while the aggregate state is `in_progress`, using TanStack Query's refetch interval, and polling stops on `ready` or `failed`. A failed job shows its reason and offers a re-upload. This is the only place in the product where a user waits on a worker, so the waiting must be legible rather than a spinner with no end.

### Visual language

Denser than the reader screens, and that divergence is expected: the maquette's editorial language serves discovery, not data entry. Colour tokens, the gold focus ring and the Gabon stripe carry over for continuity; the editorial card grid does not. Tables, compact forms and state badges take its place.

## Testing

Component and route tests with Vitest and Testing Library, sized to risk:

- `RequireRole` refuses a reader and admits a content admin;
- the staff modules are absent from the reader entry chunk;
- the deposit form maps `field_errors` onto the right inputs and shows the form-level message;
- the checklist renders `missing_for_submission` and the submit action is disabled while it is non-empty;
- the document list renders states, filters, pagination, loading, empty and error states;
- the upload control refuses a file over the limit before sending, and renders the server's refusal when it happens anyway;
- ingestion polling stops on `ready` and on `failed`, and a failed job shows its reason;
- no rendered screen contains a storage key, a `.pdf` path or a URL to a source;
- the reader routes and their tests are untouched.

## Out Of Scope

- The review workflow and its queue, the rights decision screen: slice 3.
- Organizations, quotas, support, document reports, withdrawal requests: slice 4.
- Bulk deposit, drag-and-drop of several files, resumable uploads.
- Author creation from the deposit screen beyond selecting an existing author; a proper author-identity surface is its own concern.
- Notifications of any kind.
- Any reader-facing change.
