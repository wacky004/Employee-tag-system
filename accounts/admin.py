from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Company, Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "can_use_tagging", "can_use_inventory")
    list_filter = ("is_active", "can_use_tagging", "can_use_inventory")
    search_fields = ("name", "code")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Access",
            {
                "fields": (
                    "role",
                    "role_record",
                    "company",
                    "limit_to_enabled_modules",
                    "can_access_tagging",
                    "can_access_inventory",
                )
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "role_record",
        "company",
        "limit_to_enabled_modules",
        "can_access_tagging",
        "can_access_inventory",
        "is_staff",
    )
    list_filter = (
        "role",
        "role_record",
        "company",
        "limit_to_enabled_modules",
        "can_access_tagging",
        "can_access_inventory",
        "is_staff",
        "is_superuser",
        "is_active",
    )
