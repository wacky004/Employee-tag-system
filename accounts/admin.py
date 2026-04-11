from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Access", {"fields": ("role", "role_record")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "role_record", "is_staff")
    list_filter = ("role", "role_record", "is_staff", "is_superuser", "is_active")
