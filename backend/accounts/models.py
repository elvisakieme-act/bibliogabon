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
