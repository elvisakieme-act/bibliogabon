# BiblioGABON Programme Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the validated BiblioGABON product director plan into execution-ready product, business, legal, and technical artifacts.

**Architecture:** This is a programme-level plan because BiblioGABON contains multiple independent subsystems. It creates the source-of-truth documents needed before writing subsystem implementation plans for identity, organizations, documents, reader, search, billing, administration, and analytics.

**Tech Stack:** Markdown planning artifacts now; target product stack is Django/Python, PostgreSQL, Redis/Celery, S3-compatible object storage, full-text search, Mobile Money/payment integration, and a web/mobile-first frontend.

## Global Constraints

- The current frontend maquette is not a functional specification; use it later only as UI/UX inspiration.
- BiblioGABON is a full production product to launch, not a minimal MVP experiment.
- The project is carried by an independent startup.
- The business model is hybrid: B2B institutional access first, B2C micro-subscription second, sponsored access third.
- Raw PDF/EPUB files must never be exposed directly to end users.
- Document rights, publication status, withdrawal rules, and ownership must be explicit before publication.
- Architecture must support organizations, individual users, quotas, subscriptions, and shared national catalog access.
- Technical choices must stay compatible with Django, PostgreSQL, Redis/Celery, and S3-compatible storage unless a written decision changes the stack.
- Each downstream subsystem plan must produce a working, testable slice of software.

---

## Scope Check

The product director plan covers too many independent subsystems for one implementation plan. The correct execution model is a sequence of focused plans:

1. Product and governance baseline.
2. Identity, users, roles, and organizations.
3. Document catalog and metadata.
4. Ingestion pipeline and document processing.
5. Secure reader and access control.
6. Search and discovery.
7. Subscriptions, payments, quotas, and sponsored access.
8. Administration, moderation, and support.
9. Analytics, reporting, and institutional dashboards.
10. Launch operations and go-to-market.

This master plan prepares those subsystem plans and prevents the team from building features before the rules of the product are clear.

---

### Task 1: Product Baseline And Decision Register

**Files:**
- Create: `docs/product/00-product-baseline.md`
- Create: `docs/product/00-decision-register.md`
- Read: `BiblioGABON_Plan_directeur_produit_startup.md`
- Read: `Application backend architecture BiblioGABON.docx`
- Read: `piliers.md`

**Interfaces:**
- Consumes: validated product director plan, existing backend architecture notes, and backend pillars.
- Produces: product baseline and decision register used by all later tasks.

- [ ] **Step 1: Create the product baseline headings**

Write `docs/product/00-product-baseline.md` with these exact sections:

```markdown
# BiblioGABON Product Baseline

## Product Definition
## Strategic Positioning
## Users And Organizations
## Business Model
## Product Scope
## Non-Negotiable Constraints
## Out Of Scope For Launch
## Source Documents
```

- [ ] **Step 2: Fill Product Definition**

Add this definition:

```markdown
BiblioGABON is a national academic digital library for Gabon, carried by an independent startup. It centralizes, protects, indexes, and distributes academic resources for students, teachers, researchers, institutions, and sponsored access partners.
```

- [ ] **Step 3: Fill Non-Negotiable Constraints**

Add these bullets:

```markdown
- The product is not derived from the current maquette; the maquette is reserved for later UI/UX inspiration.
- BiblioGABON is designed as a complete launchable platform, not a minimal MVP.
- Raw document files are stored privately and never exposed directly.
- Every document has an owner, publication status, access rule, and withdrawal rule.
- Institutional access and individual access coexist.
- Users attached to one institution may access the national catalog according to their subscription rights.
- Mobile-first access and low-bandwidth behavior are product priorities.
```

- [ ] **Step 4: Create the decision register**

Write `docs/product/00-decision-register.md` with this table:

```markdown
# BiblioGABON Decision Register

| ID | Date | Decision | Rationale | Impact | Owner |
|---|---|---|---|---|---|
| D001 | 2026-07-27 | Treat the maquette as UI/UX inspiration only | The product must be designed from first principles to avoid biasing scope and architecture | Frontend implementation cannot dictate product scope | Product |
| D002 | 2026-07-27 | Build a complete launchable platform, not an MVP | The concept has already been validated in a challenge | Roadmap must include core platform, business, content, and governance capabilities | Product |
| D003 | 2026-07-27 | Use hybrid monetization: B2B, B2C, sponsored access | This balances institutional revenue, student accessibility, and impact | Billing and organization modules must support several access models | Business |
| D004 | 2026-07-27 | Use Django/PostgreSQL/Redis-Celery/S3-compatible storage as initial backend direction | Existing architecture notes already converge on this pragmatic stack | Subsystem plans should assume this stack until a formal decision changes it | Tech |
```

- [ ] **Step 5: Review baseline against source documents**

Run:

```powershell
Select-String -LiteralPath 'docs/product/00-product-baseline.md','docs/product/00-decision-register.md' -Pattern 'maquette|B2B|B2C|sponsored|Django|PostgreSQL|raw document|rights'
```

Expected: output includes all major constraints.

- [ ] **Step 6: Commit**

```bash
git add docs/product/00-product-baseline.md docs/product/00-decision-register.md
git commit -m "docs: establish bibliogabon product baseline"
```

---

### Task 2: User, Role, And Organization Model

**Files:**
- Create: `docs/product/01-users-roles-organizations.md`
- Depends on: `docs/product/00-product-baseline.md`

**Interfaces:**
- Consumes: product baseline constraints.
- Produces: role and organization definitions used by identity and authorization implementation plans.

- [ ] **Step 1: Create the role matrix document**

Write `docs/product/01-users-roles-organizations.md` with these sections:

```markdown
# Users, Roles, And Organizations

## Actors
## Account Types
## Organization Model
## Access Rules
## Admin Delegation
## Edge Cases
## Acceptance Criteria
```

- [ ] **Step 2: Define actors**

Add these actors:

```markdown
- Visitor: browses public catalog and marketing pages, but cannot read restricted documents.
- Student: reads authorized documents, searches content, manages favorites, history, and subscriptions.
- Teacher/Author: submits resources, tracks usage, requests withdrawal, and manages author identity.
- Institution Admin: manages users attached to an organization, quotas, access reports, and institutional profile.
- BiblioGABON Content Admin: validates metadata, rights, document status, and publication.
- BiblioGABON Super Admin: manages platform configuration, billing, support escalation, and sensitive operations.
- Sponsor Partner: funds access for a defined group and receives agreed impact reporting.
```

- [ ] **Step 3: Define organization model**

Add:

```markdown
An organization represents an institution, school, sponsor, enterprise, or public partner that funds or manages access for a group of users. A user can have an individual subscription, an organization entitlement, or both. Documents belong to owners, not to access organizations, so the default catalog is national and shared unless a contract creates a restricted collection.
```

- [ ] **Step 4: Define access rules**

Add this rule set:

```markdown
- Public metadata is visible to visitors unless a document is fully private.
- Reading restricted pages requires an active entitlement.
- Entitlements may come from individual subscription, organization quota, sponsored campaign, or admin grant.
- Download, offline package, and full-document export require explicit permission separate from read access.
- Organization admins can add or remove eligible users but cannot change global document rights.
- Teacher/authors can request withdrawal of voluntary deposits, but institutional funds follow contract rules.
```

- [ ] **Step 5: Add acceptance criteria**

Add:

```markdown
- The document distinguishes all actors without overlapping responsibilities.
- Each actor has a clear permission boundary.
- The organization model supports both institutional and sponsored access.
- The model does not isolate the national catalog by default.
- The model leaves room for restricted collections through explicit contracts.
```

- [ ] **Step 6: Commit**

```bash
git add docs/product/01-users-roles-organizations.md
git commit -m "docs: define users roles and organizations"
```

---

### Task 3: Content Rights And Publication Governance

**Files:**
- Create: `docs/product/02-content-rights-governance.md`
- Depends on: `docs/product/00-product-baseline.md`

**Interfaces:**
- Consumes: product baseline and backend architecture notes about document categories.
- Produces: publication workflow rules used by document catalog, ingestion, admin, and legal/commercial planning.

- [ ] **Step 1: Create governance document**

Write:

```markdown
# Content Rights And Publication Governance

## Document Categories
## Ownership Rules
## Publication Workflow
## Withdrawal Rules
## Sensitive Document Policy
## Revenue Sharing Principles
## Required Contract Templates
## Acceptance Criteria
```

- [ ] **Step 2: Define document categories**

Add:

```markdown
- Voluntary teacher deposit: content submitted by its author for publication.
- Institutional fund: content supplied by a school, university, archive, lab, or organization under contract.
- Student work: thesis, dissertation, report, internship report, or academic project requiring explicit authorization.
- Open resource: public domain or openly licensed content verified before publication.
- Commercial partner content: publisher or author content distributed under revenue-sharing or licensing agreement.
```

- [ ] **Step 3: Define publication workflow**

Add these statuses:

```markdown
draft -> submitted -> rights_review -> technical_processing -> editorial_review -> published -> withdrawn -> archived
```

Add these rules:

```markdown
- A document cannot become published without owner, category, license/access rule, and withdrawal rule.
- Student work requires explicit consent and confidentiality review.
- Technical processing can run before final publication but cannot expose pages publicly.
- Withdrawn documents remain internally traceable and can be republished only through a new validation decision.
```

- [ ] **Step 4: Define required contract templates**

Add:

```markdown
- Teacher voluntary publication agreement.
- Institutional archive/fund agreement.
- Student work publication consent.
- Commercial content distribution agreement.
- Sponsored access agreement.
- Organization subscription agreement.
```

- [ ] **Step 5: Commit**

```bash
git add docs/product/02-content-rights-governance.md
git commit -m "docs: define content rights governance"
```

---

### Task 4: Commercial Offers And Partner Pipeline

**Files:**
- Create: `docs/business/01-commercial-offers.md`
- Create: `docs/business/02-partner-pipeline.md`
- Depends on: `docs/product/00-product-baseline.md`

**Interfaces:**
- Consumes: validated hybrid business model.
- Produces: offer structure used by billing, sales material, and partnership outreach.

- [ ] **Step 1: Create commercial offers document**

Write `docs/business/01-commercial-offers.md` with:

```markdown
# Commercial Offers

## Offer Principles
## B2B Institutional Offers
## B2C Micro-Subscriptions
## Sponsored Access
## Content Revenue Sharing
## Pricing Inputs To Validate
## Acceptance Criteria
```

- [ ] **Step 2: Define offer principles**

Add:

```markdown
- B2B institutional revenue is the primary business engine.
- B2C micro-subscription keeps access possible for users outside covered institutions.
- Sponsored access funds impact and adoption.
- Pricing must support FCFA, Mobile Money, and annual institutional invoicing.
- Reading access, download access, and offline access are separate commercial rights.
```

- [ ] **Step 3: Create partner pipeline document**

Write `docs/business/02-partner-pipeline.md` with this table:

```markdown
# Partner Pipeline

| Segment | Target Type | Value For Partner | BiblioGABON Ask | First Outreach Asset |
|---|---|---|---|---|
| Universities | Public and private higher education institutions | Digital library and usage reporting | Pilot agreement, content access, student communication | Institutional one-pager |
| Teachers | Faculty and researchers | Controlled publication and visibility | Voluntary content deposits and ambassador role | Teacher contributor brief |
| Telecoms | Mobile operators | Education impact and data/payment usage | Billing or bundle partnership | Usage traction report |
| Sponsors | Banks, foundations, RSE programs | Measurable education impact | Funded access cohort | Sponsored access proposal |
| Public institutions | Ministries and agencies | National academic infrastructure | Endorsement, coordination, possible funding | Policy alignment brief |
```

- [ ] **Step 4: Commit**

```bash
git add docs/business/01-commercial-offers.md docs/business/02-partner-pipeline.md
git commit -m "docs: outline commercial offers and partner pipeline"
```

---

### Task 5: Technical Subsystem Plan Index

**Files:**
- Create: `docs/technical/00-subsystem-plan-index.md`
- Depends on: `docs/product/00-product-baseline.md`
- Depends on: `docs/product/01-users-roles-organizations.md`
- Depends on: `docs/product/02-content-rights-governance.md`

**Interfaces:**
- Consumes: product, role, and content governance docs.
- Produces: ordered list of detailed implementation plans to write next.

- [ ] **Step 1: Create the subsystem index**

Write:

```markdown
# Technical Subsystem Plan Index

## Stack Direction
## Plan Sequence
## Shared Domain Concepts
## Cross-Cutting Requirements
## Readiness Gate
```

- [ ] **Step 2: Add stack direction**

Add:

```markdown
- Backend: Django/Python.
- Database: PostgreSQL.
- Async jobs: Redis + Celery.
- Object storage: S3-compatible private buckets.
- Search: PostgreSQL full-text initially, Meilisearch or Elasticsearch when needed.
- Deployment: simple production VM first, containerized services where practical.
- Configuration: environment variables only for secrets and service connections.
```

- [ ] **Step 3: Add plan sequence**

Add:

```markdown
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
```

- [ ] **Step 4: Add shared domain concepts**

Add:

```markdown
Shared concepts: User, Organization, OrganizationMembership, Entitlement, Subscription, Document, DocumentVersion, DocumentAsset, DocumentPage, Author, RightsAgreement, PublicationStatus, ProcessingJob, SearchIndexRecord, PaymentTransaction, SponsoredCampaign, AuditLog.
```

- [ ] **Step 5: Commit**

```bash
git add docs/technical/00-subsystem-plan-index.md
git commit -m "docs: index technical subsystem plans"
```

---

### Task 6: First Detailed Implementation Plan Selection

**Files:**
- Create one of:
  - `docs/superpowers/plans/2026-07-27-bibliogabon-identity-organizations.md`
  - `docs/superpowers/plans/2026-07-27-bibliogabon-catalog-metadata.md`
  - `docs/superpowers/plans/2026-07-27-bibliogabon-document-ingestion.md`
- Depends on: `docs/technical/00-subsystem-plan-index.md`

**Interfaces:**
- Consumes: subsystem index.
- Produces: first code-level implementation plan.

- [ ] **Step 1: Choose the first implementation slice**

Choose `identity-organizations` if the team is ready to start coding, because every entitlement, organization, billing, and access-control feature depends on it.

- [ ] **Step 2: Write the plan header**

Start the chosen plan with:

```markdown
# BiblioGABON Identity And Organizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first backend slice for users, roles, organizations, memberships, and entitlement foundations.

**Architecture:** Implement Django models, migrations, admin registration, service functions, and tests for identity and organization access boundaries. This slice does not implement billing or document reading yet; it creates the primitives they consume.

**Tech Stack:** Django, PostgreSQL, pytest or Django TestCase, environment-based configuration.
```

- [ ] **Step 3: Stop before writing code tasks if no Django project exists**

If no Django project exists in the selected implementation repository, record this in the plan:

```markdown
The Django project scaffold does not exist yet. The first coding task must create the backend project, test runner, app layout, environment settings, and CI-ready verification commands before identity models are added.
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-07-27-bibliogabon-identity-organizations.md
git commit -m "docs: plan identity and organizations implementation"
```

---

## Self-Review Checklist

- [ ] Every downstream subsystem is represented in the scope check.
- [ ] Product, legal/content, business, and technical foundations are separated.
- [ ] No task depends on the current maquette as a functional source.
- [ ] The hybrid business model is reflected in product, business, and technical artifacts.
- [ ] The plan creates a clear path toward code-level implementation plans.
- [ ] The first coding slice is identity and organizations unless the team chooses a different written priority.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-27-bibliogabon-programme-execution.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - execute tasks in this session using executing-plans, with checkpoints for review.

Recommended next choice: Inline Execution for Tasks 1-5 because they are document foundations, then Subagent-Driven for code-level subsystem plans.
