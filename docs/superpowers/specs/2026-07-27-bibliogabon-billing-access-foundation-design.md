# BiblioGABON Billing Access Foundation Design

## Purpose

This slice creates the backend commercial foundation for BiblioGABON. It models offers, subscriptions, payment attempts, organization quotas, and sponsored campaigns, then converts approved commercial access into existing `accounts.Entitlement` records.

It does not integrate a real Mobile Money provider, process webhooks, renew subscriptions automatically, charge cards, generate invoices, or expose a public checkout API.

## Product Rules

BiblioGABON uses a hybrid model:

- B2B institutional access is the primary revenue engine.
- B2C micro-subscriptions keep access possible for users outside institutions.
- Sponsored campaigns fund cohorts or impact groups.
- Reading, download, and offline access are separate rights.

Commercial access must never bypass `accounts.Entitlement`. Reader and document services continue to check entitlements only; billing creates and revokes the commercial source of those entitlements.

Payment attempts must be idempotent. A repeated Mobile Money callback or retry must not create duplicate transactions, subscriptions, quotas, or entitlements.

## Architecture

Create a Django app named `billing`. It depends on `accounts` and does not import reader, catalog, ingestion, processing, or search apps.

Core models:

- `CommercialOffer`: reusable offer definition for individual, organization, or sponsored access.
- `Subscription`: user or organization access period backed by an offer.
- `PaymentTransaction`: durable state for a payment attempt or manual invoice settlement.
- `OrganizationQuota`: institution-level commercial grant with seat limits and contract reference.
- `SponsoredCampaign`: sponsor-funded access pool for user enrollments.

Primary services:

```python
create_payment_transaction(...) -> PaymentTransaction
activate_subscription(subscription, at=None) -> Entitlement
activate_organization_quota(quota, at=None) -> Entitlement
enroll_user_in_sponsored_campaign(campaign, user, at=None) -> Entitlement
```

## Access Mapping

`CommercialOffer` stores the entitlement target:

- `access_right`: `read`, `download`, or `offline`;
- `scope_type`: `global`, `domain`, `collection`, or `document`;
- `scope_id`: required for non-global scopes;
- `duration_days`: controls subscription and entitlement end date.

Individual subscriptions create user entitlements with source `individual_subscription`. Organization subscriptions and quotas create organization entitlements with source `organization_quota`. Sponsored campaign enrollments create user entitlements with source `sponsored_campaign`.

`OrganizationQuota.seat_limit` is contractual capacity metadata in this slice. It records the licensed seat count for sales, support, and future reporting, but it does not yet enforce named-seat assignment. Seat assignment and per-member quota enforcement require a later organization access-management slice.

## State Rules

Payments use states: `initiated`, `pending`, `succeeded`, `failed`, `cancelled`, and `refunded`.

Subscriptions use states: `pending`, `active`, `expired`, and `cancelled`.

Organization quotas use states: `draft`, `active`, `suspended`, `expired`, and `cancelled`.

Sponsored campaigns use states: `draft`, `active`, `ended`, and `cancelled`.

Activation services must reject inactive offers, invalid target types, cancelled records, exhausted sponsored campaigns, and inconsistent date windows.

## Testing

Use pytest and pytest-django. Tests must prove:

- the billing app is installed;
- offers validate price, duration, access right, and non-global scope ids;
- subscriptions target exactly one user or organization;
- payment transactions are idempotent by key and support state transitions;
- successful individual subscription activation creates one active user entitlement;
- organization quota activation creates one organization entitlement and remains idempotent;
- sponsored campaign enrollment creates user entitlements until the funded seat limit is reached;
- cancelled or inactive commercial records cannot create entitlements;
- billing models are registered in Django admin.

## Out Of Scope

- Real Mobile Money provider integration.
- Webhook signature verification.
- Recurring renewal jobs.
- Public checkout endpoints.
- Invoice PDF generation.
- Tax, payout, and revenue-share calculations.
- Usage analytics and institutional reports.
- Named-seat assignment and per-member quota enforcement.
