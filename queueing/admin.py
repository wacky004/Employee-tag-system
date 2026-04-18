from django.contrib import admin

from .models import (
    QueueCounter,
    QueueDisplayScreen,
    QueueHistoryLog,
    QueueService,
    QueueSystemSetting,
    QueueTicket,
)


class PlatformQueueingAdminMixin:
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


@admin.register(QueueService)
class QueueServiceAdmin(PlatformQueueingAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "company",
        "max_queue_limit",
        "current_queue_number",
        "allow_priority",
        "show_in_ticket_generation",
        "is_active",
    )
    search_fields = ("name", "code", "company__name")
    list_filter = ("company", "is_active", "allow_priority")
    fieldsets = (
        (
            "Service Details",
            {
                "fields": (
                    "company",
                    "name",
                    "code",
                    "description",
                )
            },
        ),
        (
            "Queue Settings",
            {
                "fields": (
                    "max_queue_limit",
                    "current_queue_number",
                    "allow_priority",
                    "show_in_ticket_generation",
                    "is_active",
                )
            },
        ),
    )


@admin.register(QueueCounter)
class QueueCounterAdmin(PlatformQueueingAdminMixin, admin.ModelAdmin):
    list_display = ("name", "company", "assigned_services_display", "is_active")
    search_fields = ("name", "company__name", "assigned_services__name")
    list_filter = ("company", "is_active")
    filter_horizontal = ("assigned_services",)

    @admin.display(description="Assigned Services")
    def assigned_services_display(self, obj):
        return obj.assigned_services_label


@admin.register(QueueTicket)
class QueueTicketAdmin(PlatformQueueingAdminMixin, admin.ModelAdmin):
    list_display = (
        "queue_number",
        "company",
        "service",
        "status",
        "assigned_counter",
        "is_priority",
        "created_at",
    )
    search_fields = ("queue_number", "company__name", "service__name", "assigned_counter__name")
    list_filter = ("company", "status", "service", "is_priority")
    readonly_fields = ("created_at", "called_at", "completed_at")


@admin.register(QueueHistoryLog)
class QueueHistoryLogAdmin(PlatformQueueingAdminMixin, admin.ModelAdmin):
    list_display = ("ticket", "company", "service", "counter", "actor", "action", "created_at")
    search_fields = ("ticket__queue_number", "company__name", "service__name", "counter__name", "notes")
    list_filter = ("company", "action", "created_at")
    readonly_fields = ("created_at",)


@admin.register(QueueDisplayScreen)
class QueueDisplayScreenAdmin(PlatformQueueingAdminMixin, admin.ModelAdmin):
    list_display = ("name", "company", "is_active")
    search_fields = ("name", "company__name")
    list_filter = ("company", "is_active")
    filter_horizontal = ("services",)


@admin.register(QueueSystemSetting)
class QueueSystemSettingAdmin(PlatformQueueingAdminMixin, admin.ModelAdmin):
    list_display = ("company", "queue_reset_policy", "default_max_queue_per_service", "updated_at")
    search_fields = ("company__name",)
    list_filter = ("queue_reset_policy", "company")
