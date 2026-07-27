# BiblioGABON Decision Register

| ID | Date | Decision | Rationale | Impact | Owner |
|---|---|---|---|---|---|
| D001 | 2026-07-27 | Treat the maquette as UI/UX inspiration only | The product must be designed from first principles to avoid biasing scope and architecture | Frontend implementation cannot dictate product scope | Product |
| D002 | 2026-07-27 | Build a complete launchable platform, not an MVP | The concept has already been validated in a challenge | Roadmap must include core platform, business, content, and governance capabilities | Product |
| D003 | 2026-07-27 | Use hybrid monetization: B2B, B2C, sponsored access | This balances institutional revenue, student accessibility, and impact | Billing and organization modules must support several access models | Business |
| D004 | 2026-07-27 | Use Django/PostgreSQL/Redis-Celery/S3-compatible storage as initial backend direction | Existing architecture notes already converge on this pragmatic stack | Subsystem plans should assume this stack until a formal decision changes it | Tech |

## Decision Process

New structural decisions must be added here when they affect product scope, architecture, business model, content rights, launch strategy, or partner commitments.

Each decision should include:

- A clear statement of the decision.
- The reason the decision was made.
- The expected impact.
- The owner responsible for revisiting it if assumptions change.

## Open Decision Areas

- Exact B2B pricing tiers and quotas.
- Exact B2C pass durations and FCFA prices.
- First content categories to prioritize by academic domain.
- First institutional pilot targets.
- First payment aggregator or Mobile Money integration partner.
- Data retention policy and legal review process.
