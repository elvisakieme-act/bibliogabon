# BiblioGABON Decision Register

| ID | Date | Decision | Rationale | Impact | Owner |
|---|---|---|---|---|---|
| D001 | 2026-07-27 | Treat the maquette as UI/UX inspiration only | The product must be designed from first principles to avoid biasing scope and architecture | Frontend implementation cannot dictate product scope | Product |
| D002 | 2026-07-27 | Build a complete launchable platform, not an MVP | The concept has already been validated in a challenge | Roadmap must include core platform, business, content, and governance capabilities | Product |
| D003 | 2026-07-27 | Use hybrid monetization: B2B, B2C, sponsored access | This balances institutional revenue, student accessibility, and impact | Billing and organization modules must support several access models | Business |
| D004 | 2026-07-27 | Use Django/PostgreSQL/Redis-Celery/S3-compatible storage as initial backend direction | Existing architecture notes already converge on this pragmatic stack | Subsystem plans should assume this stack until a formal decision changes it | Tech |
| D005 | 2026-07-30 | Build the real web frontend in a clean `frontend/` app while preserving the maquette's UI/UX DNA | The maquette contains strong visual patterns but also mock data, demo flows, and routes outside API V1 scope | Frontend V1 must migrate visual components selectively and rebuild data/auth/routing around `/api/v1/` | Product/Tech |
| D006 | 2026-09-26 | Rebuild the ingestion pillar to its planned shape: Celery workers behind a broker, configurable object storage, OCR, page images | A synchronous stopgap had been written outside any plan and diverged from the pillar on five axes; its only real run had failed | The pipeline becomes asynchronous and replayable; production requires a broker and an S3 backend, and fails to start without them | Tech |
| D007 | 2026-09-26 | Keep the S3-compatible provider an open deployment decision, encoded nowhere in the code | Everything talks S3 through `DOCUMENT_STORAGE_ENDPOINT_URL`, so the choice can wait for real volume | Self-hosting favours SeaweedFS (Apache 2.0, built for many small files — page rendering produces ~150 objects per document); a managed zero-egress service such as R2 removes operations work and attacks the bandwidth-cost risk, at the price of the sovereignty principle | Product/Tech |
| D008 | 2026-09-27 | Give the Content Admin its own account type, distinct from Platform Staff | Its remit is bounded — metadata, rights, status, publication — while Platform Staff carries configuration, billing and sensitive operations; collapsing them handed a moderator billing power | `AccountType.CONTENT_ADMIN`; existing platform_staff accounts keep their meaning, promotion is deliberate | Tech |
| D009 | 2026-09-27 | Sponsor Partner is an organization admin of a sponsor organization, not a fifth account type | Its capabilities are those of an organization admin; a distinct type would duplicate the organization-scoped logic | The distinction lives on `Organization.organization_type`, where it already existed | Product/Tech |
| D010 | 2026-09-27 | Administrative authority comes from roles alone; a Django model permission grants nothing | Letting a permission confer moderator actions would make the whole role matrix bypassable by assigning one | Admin permission methods derive from the predicates; a test locks the bypass shut | Tech |

## Decision Process

New structural decisions must be added here when they affect product scope, architecture, business model, content rights, launch strategy, or partner commitments.

Each decision should include:

- A clear statement of the decision.
- The reason the decision was made.
- The expected impact.
- The owner responsible for revisiting it if assumptions change.

## Open Decision Areas

- Which S3-compatible provider hosts private documents in production (see D007).
- Exact B2B pricing tiers and quotas.
- Exact B2C pass durations and FCFA prices.
- First content categories to prioritize by academic domain.
- First institutional pilot targets.
- First payment aggregator or Mobile Money integration partner.
- Data retention policy and legal review process.
