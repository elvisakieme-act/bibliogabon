# Repository Guidelines

## Project Structure & Module Organization

This repository currently contains planning documents for the BiblioGABON backend, not runnable source code. The root files are:

- `piliers.md`: backend pillars covering ingestion, page streaming/DRM, full-text search, and mobile-money payments.
- `Application backend architecture BiblioGABON.docx`: architecture reference material.

When source code is added, keep it in a clear application directory such as `src/`, `app/`, or the framework default. Mirror code organization in `tests/`, place long-form design notes in `docs/`, and reserve `assets/` for diagrams, static fixtures, or sample files. Organize backend modules around the documented domains: ingestion workers, document page delivery, search indexing, subscription/session checks, and payment webhooks.

## Build, Test, and Development Commands

No package manifest, Makefile, or test runner is present yet. Add exact commands to `README.md` and update this file when the stack is chosen. Expected future examples:

- `npm install` or `pip install -r requirements.txt`: install project dependencies.
- `npm test` or `pytest`: run the automated test suite.
- `npm run dev` or `uvicorn app.main:app --reload`: start a local development server.

Run commands from the repository root unless a tool-specific document says otherwise.

## Coding Style & Naming Conventions

Follow the formatter and linter for the selected language. Use 2-space indentation for JavaScript, TypeScript, JSON, and YAML; use 4-space indentation for Python. Prefer descriptive domain names such as `ingestion_worker`, `signed_page_url`, `search_index`, and `payment_webhook`. Keep configuration values in environment variables and document required names in `.env.example`, never in committed secrets.

## Testing Guidelines

Add tests with each implementation change. Mirror source paths under `tests/` and use explicit names such as `test_payment_webhook_rejects_invalid_signature.py` or `signed-page-url.spec.ts`. Prioritize coverage for document ingestion, access control, signed URL expiry, subscription/device checks, search indexing, and mobile-money webhook state transitions.

## Commit & Pull Request Guidelines

This checkout has no Git history available, so no existing commit convention can be inferred. Use short, imperative commit messages such as `Add ingestion architecture notes` or `Implement payment webhook validation`. Pull requests should include a concise description, linked issue when available, test results, and screenshots or sample API responses for user-facing behavior.
