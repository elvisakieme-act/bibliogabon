from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.admin_mixins import PlatformStaffArea
from accounts.models import Entitlement, Organization, OrganizationMembership, User


@admin.register(User)
class BiblioGabonUserAdmin(PlatformStaffArea, UserAdmin):
    ordering = ["email"]
    list_display = ["email", "display_name", "account_type", "is_active", "is_staff"]
    list_filter = ["account_type", "is_active", "is_staff"]
    search_fields = ["email", "display_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "account_type", "phone_number")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (
            "Important dates",
            {"fields": ("last_login", "date_joined", "created_at", "updated_at")},
        ),
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
class OrganizationAdmin(PlatformStaffArea, admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "organization_type",
        "status",
        "requires_identity_verification",
        "contact_email",
    ]
    list_filter = ["organization_type", "status", "requires_identity_verification"]
    search_fields = ["name", "slug", "contact_email"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(PlatformStaffArea, admin.ModelAdmin):
    list_display = [
        "user",
        "organization",
        "role",
        "status",
        "verification_status",
        "verified_at",
        "starts_at",
        "ends_at",
    ]
    list_filter = ["role", "status", "verification_status", "organization"]
    search_fields = [
        "user__email",
        "user__display_name",
        "organization__name",
        "proof_reference",
    ]
    autocomplete_fields = ["user", "organization", "verified_by"]


@admin.register(Entitlement)
class EntitlementAdmin(PlatformStaffArea, admin.ModelAdmin):
    list_display = [
        "target",
        "source",
        "access_right",
        "scope_type",
        "scope_id",
        "starts_at",
        "ends_at",
        "revoked_at",
    ]
    list_filter = ["source", "access_right", "scope_type", "revoked_at"]
    search_fields = ["user__email", "organization__name", "scope_id", "note"]
    autocomplete_fields = ["user", "organization"]

    @admin.display(description="Target")
    def target(self, obj: Entitlement) -> str:
        if obj.user_id:
            return obj.user.email
        return obj.organization.name
