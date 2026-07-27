from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import Entitlement, Organization


def _validate_scope(scope_type: str, scope_id: str):
    if scope_type != Entitlement.ScopeType.GLOBAL and not scope_id:
        raise ValidationError("Non-global commercial scope requires scope_id")


def _validate_date_window(starts_at, ends_at):
    if starts_at and ends_at and ends_at <= starts_at:
        raise ValidationError("ends_at must be after starts_at")


class CommercialOffer(models.Model):
    class OfferType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual subscription"
        ORGANIZATION = "organization", "Organization access"
        SPONSORED = "sponsored", "Sponsored access"

    class BillingPeriod(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        SEMESTER = "semester", "Semester"
        ANNUAL = "annual", "Annual"
        CAMPAIGN = "campaign", "Campaign"

    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    offer_type = models.CharField(max_length=24, choices=OfferType.choices)
    billing_period = models.CharField(max_length=24, choices=BillingPeriod.choices)
    price_xaf = models.IntegerField()
    duration_days = models.PositiveIntegerField()
    access_right = models.CharField(max_length=16, choices=Entitlement.AccessRight.choices)
    scope_type = models.CharField(
        max_length=16,
        choices=Entitlement.ScopeType.choices,
        default=Entitlement.ScopeType.GLOBAL,
    )
    scope_id = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        if self.price_xaf < 0:
            raise ValidationError("price_xaf must not be negative")
        if self.duration_days < 1:
            raise ValidationError("duration_days must be positive")
        _validate_scope(self.scope_type, self.scope_id)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Subscription(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    offer = models.ForeignKey(CommercialOffer, on_delete=models.PROTECT, related_name="subscriptions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="billing_subscriptions",
    )
    organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="billing_subscriptions",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    entitlement = models.ForeignKey(
        Entitlement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="billing_subscriptions",
    )
    external_reference = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["starts_at", "ends_at"]),
        ]
        ordering = ["-starts_at", "-created_at"]

    def clean(self):
        if self.user_id and self.organization_id:
            raise ValidationError("Subscription cannot target both user and organization")
        if not self.user_id and not self.organization_id:
            raise ValidationError("Subscription must target a user or organization")
        _validate_date_window(self.starts_at, self.ends_at)
        if self.offer_id:
            if self.offer.offer_type == CommercialOffer.OfferType.INDIVIDUAL and not self.user_id:
                raise ValidationError("Individual offers require a user subscription target")
            if self.offer.offer_type == CommercialOffer.OfferType.ORGANIZATION and not self.organization_id:
                raise ValidationError("Organization offers require an organization subscription target")
            if self.offer.offer_type == CommercialOffer.OfferType.SPONSORED:
                raise ValidationError("Sponsored offers cannot be activated as subscriptions")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        target = self.user.email if self.user_id else self.organization.name
        return f"{target} - {self.offer.name}"


class PaymentTransaction(models.Model):
    class Provider(models.TextChoices):
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        MANUAL_INVOICE = "manual_invoice", "Manual invoice"
        CASH = "cash", "Cash"
        ADMIN = "admin", "Admin"

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_transactions",
    )
    organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_transactions",
    )
    offer = models.ForeignKey(
        CommercialOffer,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payment_transactions",
    )
    subscription = models.ForeignKey(
        Subscription,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_transactions",
    )
    provider = models.CharField(max_length=24, choices=Provider.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INITIATED)
    amount_xaf = models.IntegerField()
    currency = models.CharField(max_length=3, default="XAF")
    idempotency_key = models.CharField(max_length=180, unique=True)
    provider_reference = models.CharField(max_length=180, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    initiated_at = models.DateTimeField(default=timezone.now)
    pending_at = models.DateTimeField(null=True, blank=True)
    succeeded_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "provider"]),
            models.Index(fields=["provider_reference"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def clean(self):
        if self.user_id and self.organization_id:
            raise ValidationError("Payment cannot target both user and organization")
        if self.amount_xaf < 0:
            raise ValidationError("amount_xaf must not be negative")
        if self.currency != "XAF":
            raise ValidationError("currency must be XAF")
        if not self.idempotency_key:
            raise ValidationError("idempotency_key is required")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def mark_pending(self, *, provider_reference: str = ""):
        self.status = self.Status.PENDING
        if provider_reference:
            self.provider_reference = provider_reference
        self.pending_at = timezone.now()
        self.save(update_fields=["status", "provider_reference", "pending_at", "updated_at"])
        return self

    def mark_succeeded(self, *, provider_reference: str = ""):
        self.status = self.Status.SUCCEEDED
        if provider_reference:
            self.provider_reference = provider_reference
        self.succeeded_at = timezone.now()
        self.failure_code = ""
        self.failure_message = ""
        self.save(
            update_fields=[
                "status",
                "provider_reference",
                "succeeded_at",
                "failure_code",
                "failure_message",
                "updated_at",
            ]
        )
        return self

    def mark_failed(self, *, error_code: str, message: str):
        self.status = self.Status.FAILED
        self.retry_count += 1
        self.failure_code = error_code
        self.failure_message = message
        self.failed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "retry_count",
                "failure_code",
                "failure_message",
                "failed_at",
                "updated_at",
            ]
        )
        return self

    def __str__(self) -> str:
        return f"{self.provider} {self.amount_xaf} {self.status}"


class OrganizationQuota(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="billing_quotas")
    offer = models.ForeignKey(CommercialOffer, on_delete=models.PROTECT, related_name="organization_quotas")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    seat_limit = models.PositiveIntegerField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    entitlement = models.ForeignKey(
        Entitlement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organization_quotas",
    )
    contract_reference = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["starts_at", "ends_at"]),
        ]
        ordering = ["organization__name", "-starts_at"]

    def clean(self):
        if self.seat_limit < 1:
            raise ValidationError("seat_limit must be positive")
        _validate_date_window(self.starts_at, self.ends_at)
        if self.offer_id and self.offer.offer_type != CommercialOffer.OfferType.ORGANIZATION:
            raise ValidationError("Organization quotas require an organization offer")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.organization.name} quota"


class SponsoredCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"
        CANCELLED = "cancelled", "Cancelled"

    sponsor = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="sponsored_campaigns")
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    funded_seat_count = models.PositiveIntegerField()
    access_right = models.CharField(max_length=16, choices=Entitlement.AccessRight.choices)
    scope_type = models.CharField(
        max_length=16,
        choices=Entitlement.ScopeType.choices,
        default=Entitlement.ScopeType.GLOBAL,
    )
    scope_id = models.CharField(max_length=128, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "starts_at", "ends_at"]),
            models.Index(fields=["sponsor", "status"]),
        ]
        ordering = ["name"]

    def clean(self):
        if self.funded_seat_count < 1:
            raise ValidationError("funded_seat_count must be positive")
        _validate_date_window(self.starts_at, self.ends_at)
        _validate_scope(self.scope_type, self.scope_id)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
