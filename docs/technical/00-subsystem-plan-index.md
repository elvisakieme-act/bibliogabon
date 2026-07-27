# Technical Subsystem Plan Index

## Stack Direction

- Backend: Django/Python.
- Database: PostgreSQL.
- Async jobs: Redis + Celery.
- Object storage: S3-compatible private buckets.
- Search: PostgreSQL full-text initially, Meilisearch or Elasticsearch when needed.
- Deployment: simple production VM first, containerized services where practical.
- Configuration: environment variables only for secrets and service connections.

## Plan Sequence

1. Identity, roles, organizations, and entitlements.
2. Catalog, metadata, domains, authors, and document statuses.
3. Document upload, private storage, and ingestion job orchestration.
4. PDF/EPUB processing, OCR, page rendering, and indexing.
5. Secure reader, page API, signed URLs, session limits, and offline packages.
6. Search and discovery.
7. Billing, Mobile Money, quotas, and sponsored campaigns.
8. Admin, moderation, support, and audit logs.
9. Analytics and institutional reporting.
10. Launch hardening, observability, backups, and operations.

## Shared Domain Concepts

Shared concepts: User, Organization, OrganizationMembership, Entitlement, Subscription, Document, DocumentVersion, DocumentAsset, DocumentPage, Author, RightsAgreement, PublicationStatus, ProcessingJob, SearchIndexRecord, PaymentTransaction, SponsoredCampaign, AuditLog.

Concept boundaries:

- User: authenticated identity, not necessarily a paying customer.
- Organization: entity that funds, manages, sponsors, or reports on access.
- Entitlement: computed or stored permission to access a document, collection, feature, or time period.
- Document: intellectual resource and metadata record.
- DocumentVersion: versioned publication unit connected to source files and processing outputs.
- DocumentAsset: private raw file, generated page image, EPUB package, OCR text, cover, or derivative.
- RightsAgreement: contract or authorization proving why a document can be published.
- ProcessingJob: asynchronous work unit for ingestion, conversion, OCR, indexing, or packaging.
- PaymentTransaction: attempt, state, provider reference, and reconciliation record for money movement.
- AuditLog: durable record of sensitive administrative or access-control actions.

## Cross-Cutting Requirements

- Raw document files stay private and are never exposed as public URLs.
- Every restricted read operation must check an active entitlement.
- Every publication decision must be auditable.
- Every payment or webhook operation must be idempotent.
- Every organization-scoped report must avoid unnecessary personal reading data.
- Every background processing job must store state, error reason, retry count, and source object reference.
- Every subsystem must include tests for success, denial, and boundary conditions.
- Environment-specific values must come from configuration, not hard-coded secrets.

## Readiness Gate

Before code implementation starts, confirm:

- Product baseline is accepted.
- Roles, organizations, and access model are accepted.
- Content rights and publication workflow are accepted.
- Commercial access models are accepted.
- The target implementation repository is selected.
- The Django project location is known, or project scaffolding is included as the first implementation task.
- Verification commands are defined for the selected backend repository.

## Next Detailed Plans

Recommended next plan:

`docs/superpowers/plans/2026-07-27-bibliogabon-identity-organizations.md`

Reason: every future feature depends on identity, roles, organizations, memberships, and entitlements. Catalog publication, reader access, billing, and reporting all consume those primitives.
