from types import MethodType

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Company, Role, User


class PlatformOnlyAdminMixin:
    def has_module_permission(self, request):
        return request.user.is_authenticated and request.user.can_manage_companies()

    def has_view_permission(self, request, obj=None):
        return request.user.is_authenticated and request.user.can_manage_companies()

    def has_add_permission(self, request):
        return request.user.is_authenticated and request.user.can_manage_companies()

    def has_change_permission(self, request, obj=None):
        return request.user.is_authenticated and request.user.can_manage_companies()

    def has_delete_permission(self, request, obj=None):
        return request.user.is_authenticated and request.user.can_manage_companies()


@admin.register(Role)
class RoleAdmin(PlatformOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Company)
class CompanyAdmin(PlatformOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "can_use_tagging", "can_use_inventory")
    list_filter = ("is_active", "can_use_tagging", "can_use_inventory")
    search_fields = ("name", "code")


class BaseScopedUserAdmin(BaseUserAdmin):
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

    def _has_scoped_admin_access(self, request):
        return request.user.is_authenticated and (
            request.user.can_manage_companies()
            or (request.user.role == User.Role.SUPER_ADMIN and request.user.company_id is not None)
        )

    def has_module_permission(self, request):
        return self._has_scoped_admin_access(request)

    def has_view_permission(self, request, obj=None):
        return self._has_scoped_admin_access(request)

    def has_add_permission(self, request):
        return self._has_scoped_admin_access(request)

    def has_change_permission(self, request, obj=None):
        return self._has_scoped_admin_access(request)

    def has_delete_permission(self, request, obj=None):
        return self._has_scoped_admin_access(request)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("company", "role_record")
        if request.user.can_manage_companies():
            return queryset
        if request.user.role == User.Role.SUPER_ADMIN and request.user.company_id:
            return queryset.filter(company=request.user.company)
        return queryset.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "company" and not request.user.can_manage_companies():
            kwargs["queryset"] = Company.objects.filter(pk=request.user.company_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if not request.user.can_manage_companies():
            readonly_fields.append("company")
        return tuple(dict.fromkeys(readonly_fields))

    def save_model(self, request, obj, form, change):
        if not request.user.can_manage_companies():
            obj.company = request.user.company
        super().save_model(request, obj, form, change)


@admin.register(User)
class UserAdmin(BaseScopedUserAdmin):
    pass


class TenantAdminSite(AdminSite):
    site_header = "AquiSo Tenant Admin"
    site_title = "AquiSo Tenant Admin"
    index_title = "Tenant administration"

    def has_permission(self, request):
        return (
            request.user.is_active
            and request.user.is_authenticated
            and request.user.role == User.Role.SUPER_ADMIN
            and request.user.company_id is not None
        )


tenant_admin_site = TenantAdminSite(name="tenant_admin")


class TenantUserAdmin(BaseScopedUserAdmin):
    list_filter = (
        "role",
        "limit_to_enabled_modules",
        "can_access_tagging",
        "can_access_inventory",
        "is_staff",
        "is_active",
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.can_manage_companies():
            return fieldsets

        filtered_fieldsets = []
        for name, options in fieldsets:
            fields = options.get("fields", ())
            if name == "Permissions":
                fields = tuple(field for field in fields if field not in {"user_permissions", "groups"})
            if name == "Access":
                fields = tuple(field for field in fields if field != "role_record")
            filtered_fieldsets.append((name, {**options, "fields": fields}))
        return tuple(filtered_fieldsets)


tenant_admin_site.register(User, TenantUserAdmin)


def _platform_admin_has_permission(self, request):
    return request.user.is_active and request.user.is_authenticated and request.user.can_manage_companies()


admin.site.has_permission = MethodType(_platform_admin_has_permission, admin.site)
admin.site.site_header = "AquiSo Platform Admin"
admin.site.site_title = "AquiSo Platform Admin"
admin.site.index_title = "Platform administration"
