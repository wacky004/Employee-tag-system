from types import MethodType

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from attendance.models import AttendanceSession, CorrectionRequest, OverbreakRecord
from tagging.models import TagLog, TagType
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
    list_display = ("name", "code", "is_active", "can_use_tagging", "can_use_inventory", "can_use_queueing")
    list_filter = ("is_active", "can_use_tagging", "can_use_inventory", "can_use_queueing")
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
                    "can_access_queueing",
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
        "can_access_queueing",
        "is_staff",
    )
    list_filter = (
        "role",
        "role_record",
        "company",
        "limit_to_enabled_modules",
        "can_access_tagging",
        "can_access_inventory",
        "can_access_queueing",
        "is_staff",
        "is_superuser",
        "is_active",
    )

    def _module_is_available_for_request(self, request, module_name):
        return request.user.can_manage_companies() or request.user.company_allows_module(module_name)

    def get_list_display(self, request):
        list_display = list(super().get_list_display(request))
        if not self._module_is_available_for_request(request, "tagging") and "can_access_tagging" in list_display:
            list_display.remove("can_access_tagging")
        if not self._module_is_available_for_request(request, "inventory") and "can_access_inventory" in list_display:
            list_display.remove("can_access_inventory")
        if not self._module_is_available_for_request(request, "queueing") and "can_access_queueing" in list_display:
            list_display.remove("can_access_queueing")
        return tuple(list_display)

    def get_list_filter(self, request):
        list_filter = list(super().get_list_filter(request))
        if not self._module_is_available_for_request(request, "tagging") and "can_access_tagging" in list_filter:
            list_filter.remove("can_access_tagging")
        if not self._module_is_available_for_request(request, "inventory") and "can_access_inventory" in list_filter:
            list_filter.remove("can_access_inventory")
        if not self._module_is_available_for_request(request, "queueing") and "can_access_queueing" in list_filter:
            list_filter.remove("can_access_queueing")
        return tuple(list_filter)

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
            if request.user.company_id and not request.user.company.can_use_tagging:
                readonly_fields.append("can_access_tagging")
            if request.user.company_id and not request.user.company.can_use_inventory:
                readonly_fields.append("can_access_inventory")
            if request.user.company_id and not request.user.company.can_use_queueing:
                readonly_fields.append("can_access_queueing")
        return tuple(dict.fromkeys(readonly_fields))

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if request.user.company_id and not request.user.can_manage_companies():
            updated_fieldsets = []
            for name, options in fieldsets:
                fields = list(options.get("fields", ()))
                if name == "Access":
                    if not request.user.company.can_use_tagging and "can_access_tagging" in fields:
                        fields.remove("can_access_tagging")
                    if not request.user.company.can_use_inventory and "can_access_inventory" in fields:
                        fields.remove("can_access_inventory")
                    if not request.user.company.can_use_queueing and "can_access_queueing" in fields:
                        fields.remove("can_access_queueing")
                updated_fieldsets.append((name, {**options, "fields": tuple(fields)}))
            return tuple(updated_fieldsets)
        return tuple(fieldsets)

    def save_model(self, request, obj, form, change):
        if not request.user.can_manage_companies():
            obj.company = request.user.company
        if obj.company_id:
            if not obj.company.can_use_tagging:
                obj.can_access_tagging = False
            if not obj.company.can_use_inventory:
                obj.can_access_inventory = False
            if not obj.company.can_use_queueing:
                obj.can_access_queueing = False
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
        "can_access_queueing",
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


class TenantScopedAdminMixin:
    required_module = None

    def _has_tenant_admin_access(self, request):
        return request.user.is_authenticated and (
            request.user.can_manage_companies()
            or (request.user.role == User.Role.SUPER_ADMIN and request.user.company_id is not None)
        )

    def has_module_permission(self, request):
        if not self._has_tenant_admin_access(request):
            return False
        if self.required_module and request.user.company_id and not request.user.company_allows_module(self.required_module):
            return False
        return True

    def has_view_permission(self, request, obj=None):
        return self._has_tenant_admin_access(request)

    def has_add_permission(self, request):
        return self._has_tenant_admin_access(request)

    def has_change_permission(self, request, obj=None):
        return self._has_tenant_admin_access(request)

    def has_delete_permission(self, request, obj=None):
        return self._has_tenant_admin_access(request)


class TenantScopedTagLogAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    required_module = "tagging"
    list_display = ("employee", "tag_type", "work_date", "timestamp", "source")
    list_filter = ("tag_type", "source", "work_date")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name", "notes")

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("employee", "tag_type")
        if request.user.can_manage_companies():
            return queryset
        return queryset.filter(employee__company=request.user.company)


class TenantScopedAttendanceSessionAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    required_module = "tagging"
    list_display = (
        "employee",
        "work_date",
        "first_time_in",
        "last_time_out",
        "total_work_minutes",
        "total_lunch_minutes",
        "total_break_minutes",
        "total_bio_minutes",
        "total_overbreak_minutes",
        "missing_tag_pairs_count",
        "has_incomplete_records",
        "is_late",
    )
    list_filter = ("current_status", "is_late", "has_incomplete_records", "work_date")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name")
    readonly_fields = ("summary_notes",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("employee")
        if request.user.can_manage_companies():
            return queryset
        return queryset.filter(employee__company=request.user.company)


class TenantScopedOverbreakRecordAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    required_module = "tagging"
    list_display = ("employee", "tag_type", "work_date", "excess_minutes", "status")
    list_filter = ("status", "tag_type")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name")

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("employee", "tag_type", "attendance_session")
        if request.user.can_manage_companies():
            return queryset
        return queryset.filter(employee__company=request.user.company)

    def work_date(self, obj):
        return obj.attendance_session.work_date


class TenantScopedCorrectionRequestAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    required_module = "tagging"
    list_display = ("employee", "request_type", "target_work_date", "requested_tag_type", "status", "reviewed_by", "created_at")
    list_filter = ("request_type", "status", "target_work_date")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name", "reason", "details")
    readonly_fields = ("reviewed_at", "applied_tag_log")

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("employee", "requested_tag_type", "reviewed_by", "applied_tag_log")
        if request.user.can_manage_companies():
            return queryset
        return queryset.filter(employee__company=request.user.company)


class TenantScopedTagTypeAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    required_module = "tagging"
    list_display = ("code", "name", "category", "direction", "default_allowed_minutes", "is_active")
    list_filter = ("category", "direction", "is_active")
    search_fields = ("code", "name")

    def has_add_permission(self, request):
        return request.user.can_manage_companies()

    def has_change_permission(self, request, obj=None):
        return request.user.can_manage_companies()

    def has_delete_permission(self, request, obj=None):
        return request.user.can_manage_companies()


tenant_admin_site.register(TagLog, TenantScopedTagLogAdmin)
tenant_admin_site.register(AttendanceSession, TenantScopedAttendanceSessionAdmin)
tenant_admin_site.register(OverbreakRecord, TenantScopedOverbreakRecordAdmin)
tenant_admin_site.register(CorrectionRequest, TenantScopedCorrectionRequestAdmin)
tenant_admin_site.register(TagType, TenantScopedTagTypeAdmin)


def _platform_admin_has_permission(self, request):
    return request.user.is_active and request.user.is_authenticated and request.user.can_manage_companies()


admin.site.has_permission = MethodType(_platform_admin_has_permission, admin.site)
admin.site.site_header = "AquiSo Platform Admin"
admin.site.site_title = "AquiSo Platform Admin"
admin.site.index_title = "Platform administration"
