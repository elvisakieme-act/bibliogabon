# BiblioGABON Identity And Organizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first backend slice for users, roles, organizations, memberships, and entitlement foundations.

**Architecture:** Create a Django backend in `backend/`, then implement identity and organization primitives in a focused `accounts` app. This slice does not implement billing, documents, reading, or search yet; it creates the access primitives those modules will consume.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, PostgreSQL for production, SQLite only for local/test fallback, pytest, pytest-django, Redis/Celery reserved for later async subsystems.

## Global Constraints

- The current frontend maquette is not a functional specification; use it later only as UI/UX inspiration.
- BiblioGABON is a full production product to launch, not a minimal MVP experiment.
- The project is carried by an independent startup.
- The business model is hybrid: B2B institutional access first, B2C micro-subscription second, sponsored access third.
- Raw PDF/EPUB files must never be exposed directly to end users.
- Document rights, publication status, withdrawal rules, and ownership must be explicit before publication.
- Architecture must support organizations, individual users, quotas, subscriptions, and shared national catalog access.
- Technical choices must stay compatible with Django, PostgreSQL, Redis/Celery, and S3-compatible storage unless a written decision changes the stack.
- Identity, role, and entitlement must remain separate concepts.
- A user can have individual access, organization access, sponsored access, or several of these at once.
- The default catalog is national and shared; organization membership does not isolate documents by default.

---

## File Structure

Create this backend structure:

```text
backend/
  .env.example
  manage.py
  pyproject.toml
  pytest.ini
  accounts/
    __init__.py
    admin.py
    apps.py
    models.py
    services.py
    tests/
      __init__.py
      test_bootstrap.py
      test_user_model.py
      test_organizations.py
      test_entitlements.py
      test_access_services.py
  config/
    __init__.py
    asgi.py
    settings.py
    urls.py
    wsgi.py
```

Responsibility boundaries:

- `config/settings.py`: project configuration, installed apps, database, auth model, timezone, and test-safe defaults.
- `accounts/models.py`: persistent identity, organization, membership, and entitlement data model.
- `accounts/services.py`: access-check functions used later by reader, catalog, billing, and admin modules.
- `accounts/admin.py`: Django admin visibility for support and operational review.
- `accounts/tests/`: one behavior group per file.

---

### Task 1: Backend Scaffold And Test Runner

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/pytest.ini`
- Create: `backend/.env.example`
- Create: `backend/manage.py`
- Create: `backend/config/__init__.py`
- Create: `backend/config/settings.py`
- Create: `backend/config/urls.py`
- Create: `backend/config/asgi.py`
- Create: `backend/config/wsgi.py`
- Create: `backend/accounts/__init__.py`
- Create: `backend/accounts/apps.py`
- Test: `backend/accounts/tests/__init__.py`
- Test: `backend/accounts/tests/test_bootstrap.py`

**Interfaces:**
- Consumes: no backend code.
- Produces: importable Django project using `config.settings` and installable `accounts` app.

- [ ] **Step 1: Write the failing bootstrap test**

Create `backend/accounts/tests/test_bootstrap.py`:

```python
from django.conf import settings
from django.contrib.auth import get_user_model


def test_project_uses_custom_user_model():
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert get_user_model().__name__ == "User"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend
pytest accounts/tests/test_bootstrap.py -q
```

Expected: FAIL because the Django project, `accounts.User`, or settings are not implemented yet.

- [ ] **Step 3: Create `pyproject.toml`**

Create `backend/pyproject.toml`:

```toml
[project]
name = "bibliogabon-backend"
version = "0.1.0"
description = "BiblioGABON backend"
requires-python = ">=3.12"
dependencies = [
  "Django>=5.2,<6.0",
  "dj-database-url>=2.2,<3.0",
  "psycopg[binary]>=3.2,<4.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3,<9.0",
  "pytest-django>=4.9,<5.0",
]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
python_files = ["test_*.py", "*_test.py"]
testpaths = ["accounts/tests"]
```

- [ ] **Step 4: Create `pytest.ini`**

Create `backend/pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py *_test.py
testpaths = accounts/tests
```

- [ ] **Step 5: Create environment example**

Create `backend/.env.example`:

```dotenv
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://bibliogabon:bibliogabon@localhost:5432/bibliogabon
```

- [ ] **Step 6: Create Django entrypoint**

Create `backend/manage.py`:

```python
#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Create settings**

Create `backend/config/settings.py`:

```python
from pathlib import Path
import os

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
    )
}

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Libreville"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

- [ ] **Step 8: Create URL and server files**

Create `backend/config/urls.py`:

```python
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
```

Create `backend/config/asgi.py`:

```python
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
```

Create `backend/config/wsgi.py`:

```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
```

- [ ] **Step 9: Create accounts app shell**

Create `backend/accounts/apps.py`:

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
```

Create empty files:

```text
backend/accounts/__init__.py
backend/accounts/tests/__init__.py
```

- [ ] **Step 10: Run test and observe the next expected failure**

Run:

```bash
cd backend
pytest accounts/tests/test_bootstrap.py -q
```

Expected: FAIL because `accounts.User` has not been implemented yet.

- [ ] **Step 11: Commit**

```bash
git add backend
git commit -m "chore: scaffold django backend"
```

---

### Task 2: Custom User Model

**Files:**
- Modify: `backend/accounts/models.py`
- Create: `backend/accounts/tests/test_user_model.py`
- Generate: `backend/accounts/migrations/0001_initial.py`

**Interfaces:**
- Consumes: `AUTH_USER_MODEL = "accounts.User"`.
- Produces: `accounts.models.User`, email-based authentication identity, and account type choices.

- [ ] **Step 1: Write failing user model tests**

Create `backend/accounts/tests/test_user_model.py`:

```python
import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_create_user_with_email_identity():
    User = get_user_model()

    user = User.objects.create_user(
        email="aline@example.ga",
        password="secure-passphrase",
        display_name="Aline NZE",
        account_type=User.AccountType.INDIVIDUAL,
    )

    assert user.email == "aline@example.ga"
    assert user.username is None
    assert user.display_name == "Aline NZE"
    assert user.account_type == User.AccountType.INDIVIDUAL
    assert user.check_password("secure-passphrase")
    assert str(user) == "Aline NZE"


@pytest.mark.django_db
def test_create_superuser_sets_staff_and_superuser_flags():
    User = get_user_model()

    user = User.objects.create_superuser(
        email="admin@bibliogabon.ga",
        password="secure-passphrase",
    )

    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.account_type == User.AccountType.PLATFORM_STAFF
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest accounts/tests/test_user_model.py -q
```

Expected: FAIL because `User` and its manager are not implemented.

- [ ] **Step 3: Implement custom user model**

Create `backend/accounts/models.py`:

```python
from __future__ import annotations

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("account_type", User.AccountType.PLATFORM_STAFF)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class AccountType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual learner"
        TEACHER_AUTHOR = "teacher_author", "Teacher/author"
        ORGANIZATION_ADMIN = "organization_admin", "Organization admin"
        PLATFORM_STAFF = "platform_staff", "Platform staff"

    username = None
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=160, blank=True)
    account_type = models.CharField(
        max_length=32,
        choices=AccountType.choices,
        default=AccountType.INDIVIDUAL,
    )
    phone_number = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def __str__(self) -> str:
        return self.display_name or self.email
```

- [ ] **Step 4: Create and inspect migration**

Run:

```bash
cd backend
python manage.py makemigrations accounts
```

Expected: Django creates `backend/accounts/migrations/0001_initial.py` with the `User` table.

- [ ] **Step 5: Run user tests**

Run:

```bash
cd backend
pytest accounts/tests/test_bootstrap.py accounts/tests/test_user_model.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/accounts backend/config backend/pyproject.toml backend/pytest.ini
git commit -m "feat: add custom user identity model"
```

---

### Task 3: Organizations And Memberships

**Files:**
- Modify: `backend/accounts/models.py`
- Create: `backend/accounts/tests/test_organizations.py`
- Generate: `backend/accounts/migrations/0002_organization_membership.py`

**Interfaces:**
- Consumes: `accounts.models.User`.
- Produces: `Organization` and `OrganizationMembership` models.

- [ ] **Step 1: Write failing organization tests**

Create `backend/accounts/tests/test_organizations.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from accounts.models import Organization, OrganizationMembership


@pytest.mark.django_db
def test_create_organization_and_active_membership():
    User = get_user_model()
    user = User.objects.create_user(email="student@example.ga", password="pass")
    organization = Organization.objects.create(
        name="Universite Omar Bongo",
        slug="uob",
        organization_type=Organization.OrganizationType.UNIVERSITY,
    )

    membership = OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=OrganizationMembership.Role.MEMBER,
        status=OrganizationMembership.Status.ACTIVE,
    )

    assert str(organization) == "Universite Omar Bongo"
    assert membership.is_active is True
    assert str(membership) == "student@example.ga @ Universite Omar Bongo"


@pytest.mark.django_db
def test_user_can_have_only_one_membership_record_per_organization():
    User = get_user_model()
    user = User.objects.create_user(email="student@example.ga", password="pass")
    organization = Organization.objects.create(name="USTM", slug="ustm")

    OrganizationMembership.objects.create(organization=organization, user=user)

    with pytest.raises(IntegrityError):
        OrganizationMembership.objects.create(organization=organization, user=user)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest accounts/tests/test_organizations.py -q
```

Expected: FAIL because `Organization` and `OrganizationMembership` are not implemented.

- [ ] **Step 3: Add organization models**

Append to `backend/accounts/models.py` after `User`:

```python
class Organization(models.Model):
    class OrganizationType(models.TextChoices):
        UNIVERSITY = "university", "University"
        SCHOOL = "school", "School"
        ENTERPRISE = "enterprise", "Enterprise"
        SPONSOR = "sponsor", "Sponsor"
        PUBLIC_INSTITUTION = "public_institution", "Public institution"
        FOUNDATION = "foundation", "Foundation"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    organization_type = models.CharField(
        max_length=32,
        choices=OrganizationType.choices,
        default=OrganizationType.UNIVERSITY,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    contact_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        ADMIN = "admin", "Admin"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ENDED = "ended", "Ended"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="uniq_membership_per_org_user",
            )
        ]
        ordering = ["organization__name", "user__email"]

    @property
    def is_active(self) -> bool:
        now = timezone.now()
        if self.status != self.Status.ACTIVE:
            return False
        if self.ends_at and self.ends_at <= now:
            return False
        return self.organization.status == Organization.Status.ACTIVE

    def __str__(self) -> str:
        return f"{self.user.email} @ {self.organization.name}"
```

- [ ] **Step 4: Create migration**

Run:

```bash
cd backend
python manage.py makemigrations accounts
```

Expected: Django creates `0002_organization_membership.py`.

- [ ] **Step 5: Run organization tests**

Run:

```bash
cd backend
pytest accounts/tests/test_organizations.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/accounts
git commit -m "feat: add organizations and memberships"
```

---

### Task 4: Entitlements And Access Checks

**Files:**
- Modify: `backend/accounts/models.py`
- Create: `backend/accounts/services.py`
- Create: `backend/accounts/tests/test_entitlements.py`
- Create: `backend/accounts/tests/test_access_services.py`
- Generate: `backend/accounts/migrations/0003_entitlement.py`

**Interfaces:**
- Consumes: `User`, `Organization`, `OrganizationMembership`.
- Produces: `Entitlement`, `AccessRight`, `ScopeType`, and `user_has_entitlement()`.

- [ ] **Step 1: Write failing entitlement model tests**

Create `backend/accounts/tests/test_entitlements.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Entitlement


@pytest.mark.django_db
def test_direct_entitlement_is_active_inside_valid_window():
    User = get_user_model()
    user = User.objects.create_user(email="reader@example.ga", password="pass")
    entitlement = Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(days=1),
        ends_at=timezone.now() + timezone.timedelta(days=1),
    )

    assert entitlement.is_active_at(timezone.now()) is True


@pytest.mark.django_db
def test_expired_entitlement_is_inactive():
    User = get_user_model()
    user = User.objects.create_user(email="reader@example.ga", password="pass")
    entitlement = Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(days=3),
        ends_at=timezone.now() - timezone.timedelta(days=1),
    )

    assert entitlement.is_active_at(timezone.now()) is False
```

- [ ] **Step 2: Write failing service tests**

Create `backend/accounts/tests/test_access_services.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Entitlement, Organization, OrganizationMembership
from accounts.services import user_has_entitlement


@pytest.mark.django_db
def test_user_has_direct_read_entitlement():
    User = get_user_model()
    user = User.objects.create_user(email="reader@example.ga", password="pass")
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(hours=1),
        ends_at=timezone.now() + timezone.timedelta(hours=1),
    )

    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.django_db
def test_user_in_active_organization_inherits_organization_entitlement():
    User = get_user_model()
    user = User.objects.create_user(email="student@example.ga", password="pass")
    organization = Organization.objects.create(name="UOB", slug="uob")
    OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        status=OrganizationMembership.Status.ACTIVE,
    )
    Entitlement.objects.create(
        organization=organization,
        source=Entitlement.Source.ORGANIZATION_QUOTA,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(hours=1),
        ends_at=timezone.now() + timezone.timedelta(hours=1),
    )

    assert user_has_entitlement(user, Entitlement.AccessRight.READ) is True


@pytest.mark.django_db
def test_download_requires_download_right_not_only_read_right():
    User = get_user_model()
    user = User.objects.create_user(email="reader@example.ga", password="pass")
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(hours=1),
        ends_at=timezone.now() + timezone.timedelta(hours=1),
    )

    assert user_has_entitlement(user, Entitlement.AccessRight.DOWNLOAD) is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd backend
pytest accounts/tests/test_entitlements.py accounts/tests/test_access_services.py -q
```

Expected: FAIL because `Entitlement` and `user_has_entitlement()` are not implemented.

- [ ] **Step 4: Add Entitlement model**

Append to `backend/accounts/models.py`:

```python
class Entitlement(models.Model):
    class Source(models.TextChoices):
        INDIVIDUAL_SUBSCRIPTION = "individual_subscription", "Individual subscription"
        ORGANIZATION_QUOTA = "organization_quota", "Organization quota"
        SPONSORED_CAMPAIGN = "sponsored_campaign", "Sponsored campaign"
        ADMIN_GRANT = "admin_grant", "Admin grant"

    class AccessRight(models.TextChoices):
        READ = "read", "Read"
        DOWNLOAD = "download", "Download"
        OFFLINE = "offline", "Offline"

    class ScopeType(models.TextChoices):
        GLOBAL = "global", "Global"
        DOMAIN = "domain", "Domain"
        COLLECTION = "collection", "Collection"
        DOCUMENT = "document", "Document"

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="entitlements",
    )
    organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="entitlements",
    )
    source = models.CharField(max_length=32, choices=Source.choices)
    access_right = models.CharField(max_length=16, choices=AccessRight.choices)
    scope_type = models.CharField(
        max_length=16,
        choices=ScopeType.choices,
        default=ScopeType.GLOBAL,
    )
    scope_id = models.CharField(max_length=128, blank=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "access_right", "scope_type"]),
            models.Index(fields=["organization", "access_right", "scope_type"]),
            models.Index(fields=["starts_at", "ends_at"]),
        ]
        ordering = ["-starts_at", "-created_at"]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.user_id and self.organization_id:
            raise ValidationError("Entitlement cannot target both user and organization")
        if not self.user_id and not self.organization_id:
            raise ValidationError("Entitlement must target a user or organization")
        if self.scope_type != self.ScopeType.GLOBAL and not self.scope_id:
            raise ValidationError("Non-global entitlement requires scope_id")

    def is_active_at(self, at=None) -> bool:
        at = at or timezone.now()
        if self.revoked_at is not None:
            return False
        if self.starts_at > at:
            return False
        if self.ends_at is not None and self.ends_at <= at:
            return False
        return True

    def matches_scope(self, scope_type: str, scope_id: str = "") -> bool:
        if self.scope_type == self.ScopeType.GLOBAL:
            return True
        return self.scope_type == scope_type and self.scope_id == scope_id

    def __str__(self) -> str:
        target = self.user.email if self.user_id else self.organization.name
        return f"{target}: {self.access_right} ({self.scope_type})"
```

- [ ] **Step 5: Add access service**

Create `backend/accounts/services.py`:

```python
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from accounts.models import Entitlement, OrganizationMembership, User


def active_organization_ids_for_user(user: User, at=None) -> list[int]:
    at = at or timezone.now()
    memberships = OrganizationMembership.objects.filter(
        user=user,
        status=OrganizationMembership.Status.ACTIVE,
        starts_at__lte=at,
        organization__status="active",
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))

    return list(memberships.values_list("organization_id", flat=True))


def user_has_entitlement(
    user: User,
    access_right: str,
    scope_type: str = Entitlement.ScopeType.GLOBAL,
    scope_id: str = "",
    at=None,
) -> bool:
    at = at or timezone.now()
    organization_ids = active_organization_ids_for_user(user, at=at)
    candidates = Entitlement.objects.filter(
        Q(user=user) | Q(user__isnull=True, organization_id__in=organization_ids),
        access_right=access_right,
        starts_at__lte=at,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))

    for entitlement in candidates:
        if entitlement.is_active_at(at) and entitlement.matches_scope(scope_type, scope_id):
            return True
    return False
```

- [ ] **Step 6: Create migration**

Run:

```bash
cd backend
python manage.py makemigrations accounts
```

Expected: Django creates `0003_entitlement.py`.

- [ ] **Step 7: Run entitlement tests**

Run:

```bash
cd backend
pytest accounts/tests/test_entitlements.py accounts/tests/test_access_services.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/accounts
git commit -m "feat: add entitlements and access checks"
```

---

### Task 5: Django Admin And Full Verification

**Files:**
- Modify: `backend/accounts/admin.py`
- Create: `backend/accounts/tests/test_admin_registration.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Consumes: `User`, `Organization`, `OrganizationMembership`, `Entitlement`.
- Produces: Django admin registration and final verification commands.

- [ ] **Step 1: Write failing admin registration test**

Create `backend/accounts/tests/test_admin_registration.py`:

```python
from django.contrib import admin

from accounts.models import Entitlement, Organization, OrganizationMembership, User


def test_core_identity_models_are_registered_in_admin():
    assert User in admin.site._registry
    assert Organization in admin.site._registry
    assert OrganizationMembership in admin.site._registry
    assert Entitlement in admin.site._registry
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest accounts/tests/test_admin_registration.py -q
```

Expected: FAIL because admin classes are not registered yet.

- [ ] **Step 3: Register models in Django admin**

Create `backend/accounts/admin.py`:

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import Entitlement, Organization, OrganizationMembership, User


@admin.register(User)
class BiblioGabonUserAdmin(UserAdmin):
    ordering = ["email"]
    list_display = ["email", "display_name", "account_type", "is_active", "is_staff"]
    list_filter = ["account_type", "is_active", "is_staff"]
    search_fields = ["email", "display_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "account_type", "phone_number")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "display_name", "account_type", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "organization_type", "status", "contact_email"]
    list_filter = ["organization_type", "status"]
    search_fields = ["name", "slug", "contact_email"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role", "status", "starts_at", "ends_at"]
    list_filter = ["role", "status", "organization"]
    search_fields = ["user__email", "user__display_name", "organization__name"]
    autocomplete_fields = ["user", "organization"]


@admin.register(Entitlement)
class EntitlementAdmin(admin.ModelAdmin):
    list_display = ["target", "source", "access_right", "scope_type", "scope_id", "starts_at", "ends_at", "revoked_at"]
    list_filter = ["source", "access_right", "scope_type", "revoked_at"]
    search_fields = ["user__email", "organization__name", "scope_id", "note"]
    autocomplete_fields = ["user", "organization"]

    @admin.display(description="Target")
    def target(self, obj: Entitlement) -> str:
        if obj.user_id:
            return obj.user.email
        return obj.organization.name
```

- [ ] **Step 4: Run full test suite**

Run:

```bash
cd backend
pytest -q
```

Expected: PASS for all tests in `accounts/tests`.

- [ ] **Step 5: Run Django checks**

Run:

```bash
cd backend
python manage.py check
```

Expected: `System check identified no issues`.

- [ ] **Step 6: Run migrations locally**

Run:

```bash
cd backend
python manage.py migrate
```

Expected: all Django and `accounts` migrations apply successfully.

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat: expose identity primitives in admin"
```

---

## Self-Review Checklist

- [ ] Backend scaffold exists in `backend/`.
- [ ] `AUTH_USER_MODEL` is set to `accounts.User`.
- [ ] User identity uses email login and no username field.
- [ ] Identity, role, and entitlement remain separate concepts.
- [ ] Organization membership does not delete the user account when access ends.
- [ ] Organization entitlements are inherited only through active memberships.
- [ ] Download and offline rights are separate from read rights.
- [ ] Global entitlements match any future document scope.
- [ ] Non-global entitlements require `scope_id`.
- [ ] The full test suite passes with `pytest -q`.
- [ ] Django system checks pass with `python manage.py check`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-27-bibliogabon-identity-organizations.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - execute tasks in this session using executing-plans, with checkpoints for review.

Recommended next choice: Inline Execution for Task 1 only, because the backend does not exist yet; after the scaffold is stable, continue task-by-task with verification after each slice.
