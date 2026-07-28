# BiblioGABON Analytics Reporting Design

## Purpose

This slice creates the backend foundation for privacy-conscious analytics and institutional reporting. It gives BiblioGABON staff a reliable way to generate organization-level usage, access, commercial, and support summaries without exposing personal reading behavior.

It does not create a public dashboard, BI warehouse, CSV/PDF export, real-time analytics pipeline, recommendation engine, or external analytics integration.

## Product Rules

Institutional reporting must help universities, sponsors, schools, and public partners understand the value of their access agreements while protecting readers. Reports may show aggregate usage by day, document, academic domain, access model, entitlement status, quota, payment status, and support status.

Reports must not expose user emails, user IDs, reader session keys, IP addresses, user agents, individual page paths, or per-reader history. Existing reader logs remain operational source data; analytics persists only aggregate or generated-report records.

Because reader sessions do not yet store the exact entitlement source used for access, organization attribution is conservative. A reading event can be attributed to an organization only when the user had exactly one active organization membership at the activity timestamp. Ambiguous multi-organization activity is excluded from organization-scoped reports and may be counted only in a future platform-level aggregate.

## Architecture

Create a Django app named `analytics`. It may depend on `accounts`, `catalog`, `document_reader`, `billing`, and `operations`. Other apps should not need to import analytics directly in this slice.

Core models:

- `DailyUsageAggregate`: one aggregate row per date, organization, document, academic domain, and access model.
- `InstitutionReport`: generated report for one organization and date range, storing a structured metrics snapshot.
- `AnalyticsRun`: technical execution record for report or aggregate generation.

Primary services:

```python
build_daily_usage_aggregate(day) -> list[DailyUsageAggregate]
generate_institution_report(organization, period_start, period_end, generated_by=None) -> InstitutionReport
serialize_institution_report(report) -> dict
```

Report generation should be synchronous in this slice. `AnalyticsRun` records enough state to move the same workflow to Celery later: `status`, `run_type`, `period_start`, `period_end`, `started_at`, `finished_at`, `error_message`, and JSON metadata.

## Aggregate Metrics

`DailyUsageAggregate` stores:

- `date`;
- optional `organization`;
- optional `document`;
- optional `academic_domain`;
- `access_model`;
- `reader_session_count`;
- `page_view_count`;
- `distinct_document_count`;
- `created_at` and `updated_at`.

Aggregates are idempotent for the same date and dimensional keys. Rebuilding a day updates the existing row instead of creating duplicates.

## Institutional Report Metrics

`InstitutionReport.metrics` must include organization-level values only:

- active member count for the period end date;
- active, expired, and revoked organization entitlements;
- active organization quotas and seat-limit summary;
- active organization subscriptions;
- successful and failed organization payment totals in XAF;
- support tickets opened and resolved during the period;
- reading sessions and page views grouped by day, academic domain, document, and access model.

The report may include document titles and domain names because those are catalog metadata, not personal reader data. It must not include any user-level field.

Generating a report should create an `operations.AuditLog` event when the operations app is available. The audit event records the generator, organization, period, and report id.

## Admin Behavior

Register analytics models in Django Admin. Aggregates and generated reports are read-only in this slice; staff-triggered generation goes through service functions. Admin lists should support filtering by organization, date range, run status, access model, and created timestamp.

Staff users may inspect report metrics JSON, but they should not edit aggregate counters manually through admin forms.

## Testing

Use pytest and pytest-django. Tests must prove:

- the `analytics` app is installed;
- daily aggregate generation creates idempotent organization usage rows;
- ambiguous multi-organization reading activity is excluded from organization reports;
- institution reports include access, quota, payment, support, and usage metrics;
- generated report payloads contain no forbidden personal keys or reader session identifiers;
- report generation creates an audit event;
- analytics models are registered in Django Admin with read-only protections.

## Out Of Scope

- Custom frontend dashboard.
- CSV, Excel, or PDF exports.
- Raw search-query analytics.
- Per-user reading history.
- Exact entitlement-source attribution in reader sessions.
- Real-time streaming analytics.
- External BI or analytics providers.
- Forecasting, recommendations, or machine learning.
