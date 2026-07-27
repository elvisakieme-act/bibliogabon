# Users, Roles, And Organizations

## Actors

- Visitor: browses public catalog and marketing pages, but cannot read restricted documents.
- Student: reads authorized documents, searches content, manages favorites, history, and subscriptions.
- Teacher/Author: submits resources, tracks usage, requests withdrawal, and manages author identity.
- Institution Admin: manages users attached to an organization, quotas, access reports, and institutional profile.
- BiblioGABON Content Admin: validates metadata, rights, document status, and publication.
- BiblioGABON Super Admin: manages platform configuration, billing, support escalation, and sensitive operations.
- Sponsor Partner: funds access for a defined group and receives agreed impact reporting.

## Account Types

Accounts must separate identity, role, and entitlement.

- Identity: the person or service account that authenticates.
- Role: what the account is allowed to manage.
- Entitlement: what the account is allowed to access or read.

Initial account types:

- Individual learner account: usually a student or independent user with direct subscription or sponsored access.
- Teacher/author account: a contributor who may also consume documents as a reader.
- Organization admin account: a delegated manager for an institution, school, company, sponsor, or public partner.
- Platform staff account: BiblioGABON internal account for content, support, billing, or super administration.

## Organization Model

An organization represents an institution, school, sponsor, enterprise, or public partner that funds or manages access for a group of users. A user can have an individual subscription, an organization entitlement, or both. Documents belong to owners, not to access organizations, so the default catalog is national and shared unless a contract creates a restricted collection.

Organization concepts:

- Organization: legal or operational entity buying, sponsoring, or managing access.
- OrganizationMembership: link between user and organization, with status and role.
- OrganizationQuota: commercial limit such as active seats, named users, domain access, or funded period.
- OrganizationEntitlement: access right granted by an organization to one or more users.
- RestrictedCollection: optional collection limited by contract, not the default catalog behavior.

## Access Rules

- Public metadata is visible to visitors unless a document is fully private.
- Reading restricted pages requires an active entitlement.
- Entitlements may come from individual subscription, organization quota, sponsored campaign, or admin grant.
- Download, offline package, and full-document export require explicit permission separate from read access.
- Organization admins can add or remove eligible users but cannot change global document rights.
- Teacher/authors can request withdrawal of voluntary deposits, but institutional funds follow contract rules.

Additional rules:

- A user with several entitlements receives the union of valid read permissions, unless a document is explicitly contract-restricted.
- An expired entitlement must stop new restricted reading sessions immediately.
- Active reading sessions may be ended or allowed to expire based on product policy, but raw files remain private in all cases.
- Organization removal stops access granted by that organization but must not delete the user account.
- Platform admins can override access only through auditable administrative actions.

## Admin Delegation

Institution admins manage access lists and reporting for their own organization only. They can:

- Invite, approve, suspend, or remove members from their organization.
- View quota usage and high-level reading reports agreed in the contract.
- Export permitted membership and usage summaries.
- Request support for billing, access, or content issues.

Institution admins cannot:

- Publish or remove documents globally unless separately granted content-admin rights.
- Access personal reading histories beyond aggregated reporting agreed by policy.
- Modify contracts, global pricing, platform roles, or document rights.
- See documents in private processing states.

## Edge Cases

- A student changes university: keep the user account, end the old membership, and grant new organization access if eligible.
- A user has both individual and institution access: the product should preserve the individual subscription and add institution entitlement without duplication.
- An institution has no official email system: allow admin-managed user lists, invitation codes, or verified identity workflows as alternatives.
- A sponsored campaign ends: users lose sponsored entitlement but keep their accounts, history, and any other valid subscription.
- A teacher leaves an institution: voluntary deposits remain attached to the author agreement, while institutional fund documents follow the institutional contract.

## Acceptance Criteria

- The document distinguishes all actors without overlapping responsibilities.
- Each actor has a clear permission boundary.
- The organization model supports both institutional and sponsored access.
- The model does not isolate the national catalog by default.
- The model leaves room for restricted collections through explicit contracts.
- The model can be translated into Django models and authorization tests without changing the product assumptions.
