# BiblioGABON Catalog Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the catalog metadata backend slice for academic domains, authors, document records, rights agreements, publication status, and document-scoped entitlement compatibility.

**Architecture:** Create a dedicated Django app named `catalog`. Keep identity and entitlement ownership in `accounts`; the catalog app exposes stable document metadata and `Document.entitlement_scope_id` for later reader/access modules. This slice stores governance metadata only and does not implement file ingestion, page rendering, search, billing, or reader sessions.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, pytest, pytest-django, SQLite local/test fallback, PostgreSQL production compatibility.

## Global Constraints

- The current frontend maquette is UI/UX inspiration only, not a functional source.
- BiblioGABON is a full launchable product, not a minimal MVP.
- Raw PDF/EPUB files must never be exposed directly to users.
- Every publishable document must have owner/rights holder, document category, access model, withdrawal rule, author metadata, and publication status.
- The default catalog is national and shared; organization membership does not isolate documents by default.
- `accounts` remains responsible for users, organizations, memberships, and entitlements.
- `catalog` must not create a foreign key from `accounts.Entitlement` to `catalog.Document`.
- Document-specific access must use `Entitlement.ScopeType.DOCUMENT` plus `Document.entitlement_scope_id`.

---

## File Structure

```text
backend/
  catalog/
    __init__.py
    admin.py
    apps.py
    models.py
    services.py
    migrations/
      __init__.py
    tests/
      __init__.py
      test_bootstrap.py
      test_domains.py
      test_documents.py
      test_publication_readiness.py
      test_document_entitlements.py
      test_admin_registration.py
  config/
    settings.py
  pyproject.toml
  pytest.ini
```

Responsibilities:

- `catalog/models.py`: `AcademicDomain`, `Author`, `Document`, `DocumentAuthor`, and `RightsAgreement`.
- `catalog/services.py`: publication readiness checks.
- `catalog/admin.py`: operational admin visibility.
- `catalog/tests/`: focused behavior tests.
- `config/settings.py`: install the `catalog` app.

---

### Task 1: Catalog App Scaffold And Academic Domains

**Files:**
- Create: `backend/catalog/__init__.py`
- Create: `backend/catalog/apps.py`
- Create: `backend/catalog/models.py`
- Create: `backend/catalog/migrations/__init__.py`
- Create: `backend/catalog/tests/__init__.py`
- Create: `backend/catalog/tests/test_bootstrap.py`
- Create: `backend/catalog/tests/test_domains.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/pytest.ini`
- Modify: `backend/pyproject.toml`
- Generate: `backend/catalog/migrations/0001_initial.py`

**Interfaces:**
- Consumes: Django project configuration.
- Produces: installed `catalog` app and `AcademicDomain`.

- [ ] **Step 1: Write failing bootstrap test**

Create `backend/catalog/tests/test_bootstrap.py`:

```python
from django.apps import apps


def test_catalog_app_is_installed():
    assert apps.is_installed("catalog")
```

- [ ] **Step 2: Write failing domain tests**

Create `backend/catalog/tests/test_domains.py`:

```python
import pytest
from django.db import IntegrityError

from catalog.models import AcademicDomain


@pytest.mark.django_db
def test_academic_domain_supports_parent_hierarchy():
    parent = AcademicDomain.objects.create(name="Sciences", slug="sciences")
    child = AcademicDomain.objects.create(
        name="Informatique",
        slug="informatique",
        parent=parent,
    )

    assert str(child) == "Sciences / Informatique"
    assert child.parent == parent


@pytest.mark.django_db
def test_academic_domain_slug_is_unique():
    AcademicDomain.objects.create(name="Droit", slug="droit")

    with pytest.raises(IntegrityError):
        AcademicDomain.objects.create(name="Droit public", slug="droit")
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd backend
pytest catalog/tests/test_bootstrap.py catalog/tests/test_domains.py -q
```

Expected: FAIL because `catalog` is not installed and `AcademicDomain` does not exist.

- [ ] **Step 4: Create catalog app shell**

Create `backend/catalog/apps.py`:

```python
from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
```

Create empty files:

```text
backend/catalog/__init__.py
backend/catalog/migrations/__init__.py
backend/catalog/tests/__init__.py
```

- [ ] **Step 5: Install catalog app and test discovery**

Add `"catalog"` to `INSTALLED_APPS` in `backend/config/settings.py`.

Update `backend/pytest.ini`:

```ini
testpaths = accounts/tests catalog/tests
```

Update `[tool.pytest.ini_options]` in `backend/pyproject.toml`:

```toml
testpaths = ["accounts/tests", "catalog/tests"]
```

- [ ] **Step 6: Implement `AcademicDomain`**

Create `backend/catalog/models.py`:

```python
from __future__ import annotations

from django.db import models
from django.utils import timezone


class AcademicDomain(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        if self.parent_id:
            return f"{self.parent.name} / {self.name}"
        return self.name
```

- [ ] **Step 7: Create migration**

Run:

```bash
cd backend
python manage.py makemigrations catalog
```

Expected: Django creates `catalog/migrations/0001_initial.py` with `AcademicDomain`.

- [ ] **Step 8: Run task tests**

Run:

```bash
cd backend
pytest catalog/tests/test_bootstrap.py catalog/tests/test_domains.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/catalog backend/config/settings.py backend/pytest.ini backend/pyproject.toml
git commit -m "feat: add catalog domain foundation"
```

---

### Task 2: Authors And Document Metadata

**Files:**
- Modify: `backend/catalog/models.py`
- Create: `backend/catalog/tests/test_documents.py`
- Generate: `backend/catalog/migrations/0002_author_document.py`

**Interfaces:**
- Consumes: `catalog.models.AcademicDomain`, `accounts.Organization`, `settings.AUTH_USER_MODEL`.
- Produces: `Author`, `Document`, `DocumentAuthor`, and `Document.entitlement_scope_id`.

- [ ] **Step 1: Write failing document tests**

Create `backend/catalog/tests/test_documents.py`:

```python
import pytest

from accounts.models import Organization
from catalog.models import AcademicDomain, Author, Document, DocumentAuthor


@pytest.mark.django_db
def test_document_stores_metadata_and_ordered_authors():
    domain = AcademicDomain.objects.create(name="Education", slug="education")
    owner = Organization.objects.create(name="Universite Omar Bongo", slug="uob")
    document = Document.objects.create(
        title="Pedagogie universitaire au Gabon",
        slug="pedagogie-universitaire-gabon",
        abstract="Analyse des pratiques pedagogiques universitaires.",
        language_code="fr",
        publication_year=2026,
        academic_domain=domain,
        owner_organization=owner,
        category=Document.Category.INSTITUTIONAL_FUND,
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    first = Author.objects.create(display_name="Aline NZE", normalized_name="nze aline")
    second = Author.objects.create(display_name="Brice ONDO", normalized_name="ondo brice")

    DocumentAuthor.objects.create(document=document, author=first, role=DocumentAuthor.Role.AUTHOR, position=1)
    DocumentAuthor.objects.create(document=document, author=second, role=DocumentAuthor.Role.SUPERVISOR, position=2)

    assert str(document) == "Pedagogie universitaire au Gabon"
    assert document.publication_status == Document.PublicationStatus.DRAFT
    assert document.entitlement_scope_id == str(document.pk)
    assert list(document.document_authors.order_by("position").values_list("author__display_name", flat=True)) == [
        "Aline NZE",
        "Brice ONDO",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest catalog/tests/test_documents.py -q
```

Expected: FAIL because `Author`, `Document`, and `DocumentAuthor` do not exist.

- [ ] **Step 3: Add author and document models**

Append to `backend/catalog/models.py`:

```python
class Author(models.Model):
    class AuthorType(models.TextChoices):
        PERSON = "person", "Person"
        GROUP = "group", "Group"
        INSTITUTION = "institution", "Institution"
        PUBLISHER = "publisher", "Publisher"
        OTHER = "other", "Other rights holder"

    display_name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=220)
    author_type = models.CharField(max_length=24, choices=AuthorType.choices, default=AuthorType.PERSON)
    linked_user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="author_profiles",
    )
    affiliation = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["normalized_name", "display_name"]

    def __str__(self) -> str:
        return self.display_name


class Document(models.Model):
    class Category(models.TextChoices):
        VOLUNTARY_TEACHER_DEPOSIT = "voluntary_teacher_deposit", "Voluntary teacher deposit"
        INSTITUTIONAL_FUND = "institutional_fund", "Institutional fund"
        STUDENT_WORK = "student_work", "Student work"
        OPEN_RESOURCE = "open_resource", "Open resource"
        COMMERCIAL_PARTNER_CONTENT = "commercial_partner_content", "Commercial partner content"

    class AccessModel(models.TextChoices):
        FREE = "free", "Free"
        SUBSCRIPTION = "subscription", "Subscription"
        INSTITUTION_ONLY = "institution_only", "Institution only"
        SPONSORED = "sponsored", "Sponsored"
        RESTRICTED = "restricted", "Restricted"
        PRIVATE = "private", "Private"

    class PublicationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        RIGHTS_REVIEW = "rights_review", "Rights review"
        TECHNICAL_PROCESSING = "technical_processing", "Technical processing"
        EDITORIAL_REVIEW = "editorial_review", "Editorial review"
        PUBLISHED = "published", "Published"
        WITHDRAWN = "withdrawn", "Withdrawn"
        ARCHIVED = "archived", "Archived"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    title = models.CharField(max_length=260)
    slug = models.SlugField(unique=True)
    abstract = models.TextField(blank=True)
    language_code = models.CharField(max_length=12, default="fr")
    publication_year = models.PositiveSmallIntegerField(null=True, blank=True)
    academic_domain = models.ForeignKey(
        AcademicDomain,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    owner_organization = models.ForeignKey(
        "accounts.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="owned_documents",
    )
    category = models.CharField(max_length=40, choices=Category.choices)
    access_model = models.CharField(max_length=24, choices=AccessModel.choices)
    publication_status = models.CharField(
        max_length=32,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
    )
    confidentiality_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    authors = models.ManyToManyField(Author, through="DocumentAuthor", related_name="documents")

    class Meta:
        ordering = ["title"]

    @property
    def entitlement_scope_id(self) -> str:
        return str(self.pk)

    def __str__(self) -> str:
        return self.title


class DocumentAuthor(models.Model):
    class Role(models.TextChoices):
        AUTHOR = "author", "Author"
        COAUTHOR = "coauthor", "Co-author"
        SUPERVISOR = "supervisor", "Supervisor"
        EDITOR = "editor", "Editor"
        INSTITUTIONAL_CONTRIBUTOR = "institutional_contributor", "Institutional contributor"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="document_authors")
    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name="document_authorships")
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.AUTHOR)
    position = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["document", "author"], name="uniq_author_per_document"),
            models.UniqueConstraint(fields=["document", "position"], name="uniq_author_position_per_document"),
        ]
        ordering = ["document", "position"]

    def __str__(self) -> str:
        return f"{self.author.display_name} - {self.document.title}"
```

- [ ] **Step 4: Create migration**

Run:

```bash
cd backend
python manage.py makemigrations catalog
```

Expected: Django creates `0002_author_document.py`.

- [ ] **Step 5: Run task tests**

Run:

```bash
cd backend
pytest catalog/tests/test_documents.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/catalog
git commit -m "feat: add document metadata models"
```

---

### Task 3: Rights Agreements And Publication Readiness

**Files:**
- Modify: `backend/catalog/models.py`
- Create: `backend/catalog/services.py`
- Create: `backend/catalog/tests/test_publication_readiness.py`
- Generate: `backend/catalog/migrations/0003_rightsagreement.py`

**Interfaces:**
- Consumes: `catalog.models.Document`.
- Produces: `RightsAgreement` and `document_is_publishable(document: Document) -> bool`.

- [ ] **Step 1: Write failing publication readiness tests**

Create `backend/catalog/tests/test_publication_readiness.py`:

```python
import pytest
from django.utils import timezone

from catalog.models import AcademicDomain, Author, Document, DocumentAuthor, RightsAgreement
from catalog.services import document_is_publishable


@pytest.mark.django_db
def test_document_without_rights_agreement_is_not_publishable():
    domain = AcademicDomain.objects.create(name="Droit", slug="droit")
    document = Document.objects.create(
        title="Droit public gabonais",
        slug="droit-public-gabonais",
        academic_domain=domain,
        category=Document.Category.STUDENT_WORK,
        access_model=Document.AccessModel.RESTRICTED,
    )
    author = Author.objects.create(display_name="Aline NZE", normalized_name="nze aline")
    DocumentAuthor.objects.create(document=document, author=author)

    assert document_is_publishable(document) is False


@pytest.mark.django_db
def test_document_with_complete_approved_rights_is_publishable():
    domain = AcademicDomain.objects.create(name="Medecine", slug="medecine")
    document = Document.objects.create(
        title="Sante publique au Gabon",
        slug="sante-publique-gabon",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )
    author = Author.objects.create(display_name="Brice ONDO", normalized_name="ondo brice")
    DocumentAuthor.objects.create(document=document, author=author)
    RightsAgreement.objects.create(
        document=document,
        rights_holder_name="Brice ONDO",
        agreement_type=RightsAgreement.AgreementType.OPEN_LICENSE,
        authorization_status=RightsAgreement.AuthorizationStatus.APPROVED,
        authorization_date=timezone.now().date(),
        access_model=Document.AccessModel.FREE,
        withdrawal_rule=RightsAgreement.WithdrawalRule.LICENSE_INVALID,
        reviewer_decision="Open license verified for publication.",
        audit_reference="BG-AUDIT-2026-0001",
    )

    assert document_is_publishable(document) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
pytest catalog/tests/test_publication_readiness.py -q
```

Expected: FAIL because `RightsAgreement` and `document_is_publishable()` do not exist.

- [ ] **Step 3: Add `RightsAgreement`**

Append to `backend/catalog/models.py`:

```python
class RightsAgreement(models.Model):
    class AgreementType(models.TextChoices):
        TEACHER_VOLUNTARY = "teacher_voluntary", "Teacher voluntary publication"
        INSTITUTIONAL_ARCHIVE = "institutional_archive", "Institutional archive/fund"
        STUDENT_CONSENT = "student_consent", "Student work consent"
        OPEN_LICENSE = "open_license", "Open license"
        COMMERCIAL_DISTRIBUTION = "commercial_distribution", "Commercial distribution"

    class AuthorizationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"

    class WithdrawalRule(models.TextChoices):
        AUTHOR_REQUEST = "author_request", "Author request"
        CONTRACT_TERMS = "contract_terms", "Contract terms"
        CONFIDENTIALITY_OVERRIDE = "confidentiality_override", "Confidentiality override"
        LICENSE_INVALID = "license_invalid", "License invalid"
        COMMERCIAL_TERMS = "commercial_terms", "Commercial terms"

    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name="rights_agreement")
    rights_holder_name = models.CharField(max_length=240)
    agreement_type = models.CharField(max_length=40, choices=AgreementType.choices)
    authorization_status = models.CharField(
        max_length=24,
        choices=AuthorizationStatus.choices,
        default=AuthorizationStatus.DRAFT,
    )
    authorization_date = models.DateField(null=True, blank=True)
    access_model = models.CharField(max_length=24, choices=Document.AccessModel.choices)
    withdrawal_rule = models.CharField(max_length=40, choices=WithdrawalRule.choices)
    revenue_sharing_rule = models.TextField(blank=True)
    confidentiality_terms = models.TextField(blank=True)
    consent_reference = models.CharField(max_length=160, blank=True)
    reviewer_decision = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    audit_reference = models.CharField(max_length=160, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["document__title"]

    def is_valid_for_publication(self, at=None) -> bool:
        at = at or timezone.now().date()
        if self.authorization_status != self.AuthorizationStatus.APPROVED:
            return False
        if not self.rights_holder_name or not self.authorization_date:
            return False
        if not self.withdrawal_rule or not self.reviewer_decision or not self.audit_reference:
            return False
        if self.valid_from and self.valid_from > at:
            return False
        if self.valid_until and self.valid_until < at:
            return False
        return True

    def __str__(self) -> str:
        return f"{self.document.title} rights - {self.authorization_status}"
```

- [ ] **Step 4: Add publication service**

Create `backend/catalog/services.py`:

```python
from __future__ import annotations

from catalog.models import Document


def document_is_publishable(document: Document) -> bool:
    if not document.title or not document.academic_domain_id:
        return False
    if not document.document_authors.exists():
        return False
    try:
        rights_agreement = document.rights_agreement
    except Document.rights_agreement.RelatedObjectDoesNotExist:
        return False
    return rights_agreement.is_valid_for_publication()
```

- [ ] **Step 5: Create migration**

Run:

```bash
cd backend
python manage.py makemigrations catalog
```

Expected: Django creates `0003_rightsagreement.py`.

- [ ] **Step 6: Run task tests**

Run:

```bash
cd backend
pytest catalog/tests/test_publication_readiness.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/catalog
git commit -m "feat: add rights publication readiness"
```

---

### Task 4: Document Entitlement Integration

**Files:**
- Create: `backend/catalog/tests/test_document_entitlements.py`

**Interfaces:**
- Consumes: `catalog.models.Document.entitlement_scope_id`, `accounts.models.Entitlement`, and `accounts.services.user_has_entitlement`.
- Produces: regression coverage proving document-specific entitlements do not require a FK to `Document`.

- [ ] **Step 1: Write document entitlement tests**

Create `backend/catalog/tests/test_document_entitlements.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Entitlement
from accounts.services import user_has_entitlement
from catalog.models import AcademicDomain, Document


@pytest.mark.django_db
def test_document_entitlement_grants_access_to_matching_document_only():
    User = get_user_model()
    user = User.objects.create_user(email="reader@example.ga", password="pass")
    domain = AcademicDomain.objects.create(name="Sciences sociales", slug="sciences-sociales")
    allowed = Document.objects.create(
        title="Sociologie gabonaise",
        slug="sociologie-gabonaise",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    denied = Document.objects.create(
        title="Anthropologie gabonaise",
        slug="anthropologie-gabonaise",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.ADMIN_GRANT,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=allowed.entitlement_scope_id,
        starts_at=timezone.now() - timezone.timedelta(hours=1),
        ends_at=timezone.now() + timezone.timedelta(hours=1),
    )

    assert user_has_entitlement(
        user,
        Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=allowed.entitlement_scope_id,
    ) is True
    assert user_has_entitlement(
        user,
        Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=denied.entitlement_scope_id,
    ) is False
```

- [ ] **Step 2: Run test**

Run:

```bash
cd backend
pytest catalog/tests/test_document_entitlements.py -q
```

Expected: PASS if Task 2 and the existing accounts entitlement service are correct. If it fails, fix only the catalog `entitlement_scope_id` contract unless the failure proves a real accounts regression.

- [ ] **Step 3: Commit**

```bash
git add backend/catalog/tests/test_document_entitlements.py
git commit -m "test: cover document scoped entitlements"
```

---

### Task 5: Catalog Admin And Full Verification

**Files:**
- Create: `backend/catalog/admin.py`
- Create: `backend/catalog/tests/test_admin_registration.py`

**Interfaces:**
- Consumes: all `catalog.models`.
- Produces: Django admin registration and final verification.

- [ ] **Step 1: Write failing admin registration test**

Create `backend/catalog/tests/test_admin_registration.py`:

```python
from django.contrib import admin

from catalog.models import AcademicDomain, Author, Document, DocumentAuthor, RightsAgreement


def test_catalog_models_are_registered_in_admin():
    assert AcademicDomain in admin.site._registry
    assert Author in admin.site._registry
    assert Document in admin.site._registry
    assert DocumentAuthor in admin.site._registry
    assert RightsAgreement in admin.site._registry
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
pytest catalog/tests/test_admin_registration.py -q
```

Expected: FAIL because catalog admin registrations do not exist.

- [ ] **Step 3: Register catalog models**

Create `backend/catalog/admin.py`:

```python
from django.contrib import admin

from catalog.models import AcademicDomain, Author, Document, DocumentAuthor, RightsAgreement


@admin.register(AcademicDomain)
class AcademicDomainAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["display_name", "author_type", "affiliation", "linked_user"]
    list_filter = ["author_type"]
    search_fields = ["display_name", "normalized_name", "affiliation", "contact_email"]
    autocomplete_fields = ["linked_user"]


class DocumentAuthorInline(admin.TabularInline):
    model = DocumentAuthor
    extra = 1
    autocomplete_fields = ["author"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "publication_status", "category", "access_model", "academic_domain", "owner_organization"]
    list_filter = ["publication_status", "category", "access_model", "academic_domain"]
    search_fields = ["title", "slug", "abstract"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["academic_domain", "owner_organization"]
    inlines = [DocumentAuthorInline]
    readonly_fields = ["created_at", "updated_at", "published_at", "withdrawn_at"]


@admin.register(DocumentAuthor)
class DocumentAuthorAdmin(admin.ModelAdmin):
    list_display = ["document", "author", "role", "position"]
    list_filter = ["role"]
    search_fields = ["document__title", "author__display_name"]
    autocomplete_fields = ["document", "author"]


@admin.register(RightsAgreement)
class RightsAgreementAdmin(admin.ModelAdmin):
    list_display = ["document", "rights_holder_name", "agreement_type", "authorization_status", "authorization_date"]
    list_filter = ["agreement_type", "authorization_status", "withdrawal_rule"]
    search_fields = ["document__title", "rights_holder_name", "consent_reference", "audit_reference"]
    autocomplete_fields = ["document"]
```

- [ ] **Step 4: Run catalog tests**

Run:

```bash
cd backend
pytest catalog/tests -q
```

Expected: PASS.

- [ ] **Step 5: Run full backend tests**

Run:

```bash
cd backend
pytest -q
```

Expected: PASS for accounts and catalog tests.

- [ ] **Step 6: Run Django checks and migrations**

Run:

```bash
cd backend
python manage.py check
python manage.py migrate
```

Expected: Django reports no system check issues and applies all migrations.

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat: expose catalog metadata in admin"
```

---

## Self-Review Checklist

- [ ] `catalog` is a dedicated Django app and `accounts` stays focused on identity/access primitives.
- [ ] Academic domains support hierarchy and unique slugs.
- [ ] Documents carry category, access model, publication status, owner organization, and metadata.
- [ ] Authors are separate from users, organizations, and rights holders.
- [ ] Rights agreements are explicit and required for publication readiness.
- [ ] Publication statuses include draft, submitted, rights review, technical processing, editorial review, published, withdrawn, archived, rejected, and suspended.
- [ ] `Document.entitlement_scope_id` is stable and tested with `Entitlement.ScopeType.DOCUMENT`.
- [ ] No file ingestion, raw file URL, reader, billing, or search behavior is added.
- [ ] Full tests, Django checks, and migrations pass.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-27-bibliogabon-catalog-metadata.md`.

Recommended execution: Subagent-assisted sequential implementation. The tasks touch shared model files, so implementation must be sequential; sub-agents should be used for focused review and sidecar analysis rather than parallel writes to the same files.
