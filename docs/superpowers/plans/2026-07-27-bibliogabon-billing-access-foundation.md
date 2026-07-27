# BiblioGABON Billing Access Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first billing and commercial-access backend foundation that turns paid, institutional, or sponsored access into existing BiblioGABON entitlements.

**Architecture:** Create a Django app named `billing` with commercial models and service functions. Billing depends on `accounts.Entitlement` as the access-control boundary; reader, catalog, ingestion, processing, and search do not import billing.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, pytest, pytest-django, SQLite local/test fallback, PostgreSQL production compatibility.

## Global Constraints

- Commercial access must never bypass `accounts.Entitlement`.
- Payment attempts must be idempotent by explicit idempotency key.
- Reading, download, and offline access are separate `Entitlement.AccessRight` values.
- Non-global commercial scopes require `scope_id`.
- Do not implement real Mobile Money provider integration, webhook verification, recurring renewals, public checkout endpoints, invoice PDFs, tax, payout, revenue-share, usage analytics, or institutional reports in this slice.

---

## File Structure

```text
backend/
  billing/
    __init__.py
    admin.py
    apps.py
    models.py
    services.py
    migrations/
      __init__.py
    tests/
      __init__.py
      test_admin_registration.py
      test_bootstrap.py
      test_commercial_models.py
      test_payment_transactions.py
      test_access_activation.py
  config/
    settings.py
  pyproject.toml
  pytest.ini
```

---

### Task 1: App Scaffold

**Files:**
- Create: `backend/billing/__init__.py`
- Create: `backend/billing/apps.py`
- Create: `backend/billing/migrations/__init__.py`
- Create: `backend/billing/tests/__init__.py`
- Create: `backend/billing/tests/test_bootstrap.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/pytest.ini`

**Interfaces:**
- Produces installed Django app `billing`.

- [ ] Write failing bootstrap test:

```python
from django.apps import apps


def test_billing_app_is_installed():
    assert apps.is_installed("billing")
```

- [ ] Run `python -m pytest billing/tests/test_bootstrap.py -q`; expected failure is missing app installation.
- [ ] Add `BillingConfig` with `name = "billing"`.
- [ ] Add `"billing"` to `INSTALLED_APPS`.
- [ ] Add `billing/tests` to both pytest testpath declarations.
- [ ] Run `python -m pytest billing/tests/test_bootstrap.py -q`; expected pass.
- [ ] Commit with `feat: add billing app scaffold`.

---

### Task 2: Commercial Models

**Files:**
- Create: `backend/billing/models.py`
- Create: `backend/billing/tests/test_commercial_models.py`
- Generate: `backend/billing/migrations/0001_initial.py`

**Interfaces:**
- Produces `CommercialOffer`.
- Produces `Subscription`.
- Produces `PaymentTransaction`.
- Produces `OrganizationQuota`.
- Produces `SponsoredCampaign`.

- [ ] Write failing tests for offer validation, one-target subscription validation, payment idempotency field uniqueness, quota fields, and sponsored campaign capacity fields.
- [ ] Run targeted tests; expected failure is missing models.
- [ ] Implement model enums and fields exactly from the design.
- [ ] Add `save()` methods that call `full_clean()`.
- [ ] Add model validation for price, duration, target cardinality, date windows, and non-global scope ids.
- [ ] Generate migration with `python manage.py makemigrations billing`.
- [ ] Run `python -m pytest billing/tests/test_commercial_models.py -q`; expected pass.
- [ ] Commit with `feat: add billing commercial models`.

---

### Task 3: Payment Transaction Services

**Files:**
- Create: `backend/billing/services.py`
- Create: `backend/billing/tests/test_payment_transactions.py`

**Interfaces:**
- Produces `create_payment_transaction(*, idempotency_key, amount_xaf, provider, user=None, organization=None, offer=None, subscription=None, provider_reference="", metadata=None) -> PaymentTransaction`.
- Produces `PaymentTransaction.mark_pending(provider_reference="")`.
- Produces `PaymentTransaction.mark_succeeded(provider_reference="")`.
- Produces `PaymentTransaction.mark_failed(error_code, message)`.

- [ ] Write failing tests proving repeated idempotency keys return the existing transaction, succeeded transactions record `succeeded_at`, failed transactions record retry/failure data, and conflicting idempotency reuse raises `ValueError`.
- [ ] Run targeted tests; expected failure is missing service or transition methods.
- [ ] Implement payment service and state transition methods.
- [ ] Run `python -m pytest billing/tests/test_payment_transactions.py -q`; expected pass.
- [ ] Commit with `feat: record idempotent payment transactions`.

---

### Task 4: Subscription And Quota Activation

**Files:**
- Modify: `backend/billing/services.py`
- Create: `backend/billing/tests/test_access_activation.py`

**Interfaces:**
- Produces `activate_subscription(*, subscription, at=None) -> Entitlement`.
- Produces `activate_organization_quota(*, quota, at=None) -> Entitlement`.

- [ ] Write failing tests proving active individual subscriptions create one user entitlement, active organization subscriptions create one organization entitlement, activation is idempotent, inactive offers are rejected, cancelled subscriptions are rejected, and quota activation creates one organization entitlement.
- [ ] Run targeted tests; expected failure is missing activation services.
- [ ] Implement activation services that set record status to active, set start/end dates, and create or reuse matching entitlements.
- [ ] Run `python -m pytest billing/tests/test_access_activation.py -q`; expected pass for subscription and quota tests.
- [ ] Commit with `feat: activate paid and institutional access`.

---

### Task 5: Sponsored Campaign Enrollment

**Files:**
- Modify: `backend/billing/services.py`
- Modify: `backend/billing/tests/test_access_activation.py`

**Interfaces:**
- Produces `enroll_user_in_sponsored_campaign(*, campaign, user, at=None) -> Entitlement`.

- [ ] Write failing tests proving active campaigns enroll users, repeated enrollment is idempotent, exhausted campaigns reject new users, draft/cancelled/ended campaigns reject enrollment, and campaign entitlements use source `sponsored_campaign`.
- [ ] Run targeted tests; expected failure is missing enrollment service.
- [ ] Implement campaign enrollment with funded-seat count based on active matching sponsored entitlements.
- [ ] Run `python -m pytest billing/tests/test_access_activation.py -q`; expected pass.
- [ ] Commit with `feat: enroll sponsored access users`.

---

### Task 6: Admin And Verification

**Files:**
- Create: `backend/billing/admin.py`
- Create: `backend/billing/tests/test_admin_registration.py`

**Interfaces:**
- Registers all billing models in Django admin.

- [ ] Write failing admin-registration test:

```python
from django.contrib import admin

from billing.models import CommercialOffer, OrganizationQuota, PaymentTransaction, SponsoredCampaign, Subscription


def test_billing_models_are_registered_in_admin():
    assert CommercialOffer in admin.site._registry
    assert Subscription in admin.site._registry
    assert PaymentTransaction in admin.site._registry
    assert OrganizationQuota in admin.site._registry
    assert SponsoredCampaign in admin.site._registry
```

- [ ] Run `python -m pytest billing/tests/test_admin_registration.py -q`; expected failure is unregistered models.
- [ ] Register focused model admins with list displays, filters, search fields, autocomplete fields, and read-only timestamps.
- [ ] Run admin test; expected pass.
- [ ] Run full verification:

```bash
python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
git diff --check
```

- [ ] Commit with `test: cover billing admin`.

---

### Task 7: Review And Finish

**Files:**
- Modify only files flagged by review findings.

**Interfaces:**
- Produces a reviewed, verified billing foundation ready for merge choice.

- [ ] Request code review focused on entitlement safety, idempotency, commercial state transitions, migrations, and test coverage.
- [ ] Verify each finding against the code before changing it.
- [ ] Add failing tests for behavioral fixes, implement minimal changes, and rerun targeted tests.
- [ ] Rerun full verification:

```bash
python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
git diff --check
```

- [ ] Commit review fixes if any.
- [ ] Present finishing options for the branch.
