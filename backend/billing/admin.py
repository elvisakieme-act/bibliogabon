from django.contrib import admin

from billing.models import (
    CommercialOffer,
    OrganizationQuota,
    PaymentTransaction,
    SponsoredCampaign,
    Subscription,
)


@admin.register(CommercialOffer)
class CommercialOfferAdmin(admin.ModelAdmin):
    list_display = ["name", "offer_type", "billing_period", "price_xaf", "duration_days", "is_active"]
    list_filter = ["offer_type", "billing_period", "access_right", "scope_type", "is_active"]
    search_fields = ["name", "slug", "scope_id"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["target", "offer", "status", "starts_at", "ends_at", "entitlement"]
    list_filter = ["status", "offer__offer_type", "offer__access_right"]
    search_fields = ["user__email", "user__display_name", "organization__name", "external_reference"]
    autocomplete_fields = ["offer", "user", "organization", "entitlement"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description="Target")
    def target(self, obj: Subscription) -> str:
        if obj.user_id:
            return obj.user.email
        return obj.organization.name


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ["idempotency_key", "provider", "status", "amount_xaf", "currency", "created_at"]
    list_filter = ["provider", "status", "currency"]
    search_fields = [
        "idempotency_key",
        "provider_reference",
        "user__email",
        "organization__name",
        "failure_code",
    ]
    autocomplete_fields = ["user", "organization", "offer", "subscription"]
    readonly_fields = [
        "initiated_at",
        "pending_at",
        "succeeded_at",
        "failed_at",
        "created_at",
        "updated_at",
    ]


@admin.register(OrganizationQuota)
class OrganizationQuotaAdmin(admin.ModelAdmin):
    list_display = ["organization", "offer", "status", "seat_limit", "starts_at", "ends_at"]
    list_filter = ["status", "offer__access_right", "offer__scope_type"]
    search_fields = ["organization__name", "contract_reference", "offer__name"]
    autocomplete_fields = ["organization", "offer", "entitlement"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SponsoredCampaign)
class SponsoredCampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "sponsor", "status", "funded_seat_count", "starts_at", "ends_at"]
    list_filter = ["status", "access_right", "scope_type"]
    search_fields = ["name", "slug", "sponsor__name", "scope_id"]
    autocomplete_fields = ["sponsor"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]
