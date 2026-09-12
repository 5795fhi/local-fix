from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import OTP, ProviderProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "role", "is_verified", "is_staff"]
    list_filter = ["role", "is_verified", "is_staff", "is_active"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone")}),
        ("Role & status", {"fields": ("role", "is_verified")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "role", "password1", "password2"),
        }),
    )


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "headline", "hourly_rate", "is_available", "is_approved", "rating_avg"]
    list_filter = ["is_approved", "is_available"]
    search_fields = ["user__email", "headline", "service_area"]
    filter_horizontal = ["categories"]
    actions = ["approve_providers"]

    @admin.action(description="Approve selected providers")
    def approve_providers(self, request, queryset):
        queryset.update(is_approved=True)


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ["user", "purpose", "code", "is_used", "created_at", "expires_at"]
    list_filter = ["purpose", "is_used"]
    search_fields = ["user__email"]
