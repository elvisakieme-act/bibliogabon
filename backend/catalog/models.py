from __future__ import annotations

from django.conf import settings
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


class Author(models.Model):
    class AuthorType(models.TextChoices):
        PERSON = "person", "Person"
        GROUP = "group", "Group"
        INSTITUTION = "institution", "Institution"
        PUBLISHER = "publisher", "Publisher"
        OTHER = "other", "Other rights holder"

    display_name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=220)
    author_type = models.CharField(
        max_length=24,
        choices=AuthorType.choices,
        default=AuthorType.PERSON,
    )
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
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
        VOLUNTARY_TEACHER_DEPOSIT = (
            "voluntary_teacher_deposit",
            "Voluntary teacher deposit",
        )
        INSTITUTIONAL_FUND = "institutional_fund", "Institutional fund"
        STUDENT_WORK = "student_work", "Student work"
        OPEN_RESOURCE = "open_resource", "Open resource"
        COMMERCIAL_PARTNER_CONTENT = (
            "commercial_partner_content",
            "Commercial partner content",
        )

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

    authors = models.ManyToManyField(
        Author,
        through="DocumentAuthor",
        related_name="documents",
    )

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
        INSTITUTIONAL_CONTRIBUTOR = (
            "institutional_contributor",
            "Institutional contributor",
        )

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="document_authors",
    )
    author = models.ForeignKey(
        Author,
        on_delete=models.PROTECT,
        related_name="document_authorships",
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.AUTHOR)
    position = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "author"],
                name="uniq_author_per_document",
            ),
            models.UniqueConstraint(
                fields=["document", "position"],
                name="uniq_author_position_per_document",
            ),
        ]
        ordering = ["document", "position"]

    def __str__(self) -> str:
        return f"{self.author.display_name} - {self.document.title}"


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

    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name="rights_agreement",
    )
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
        if self.access_model != self.document.access_model:
            return False
        if self.valid_from and self.valid_from > at:
            return False
        if self.valid_until and self.valid_until < at:
            return False
        return True

    def __str__(self) -> str:
        return f"{self.document.title} rights - {self.authorization_status}"
