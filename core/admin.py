from django.contrib import admin

from .models import Announcement, SystemSetting


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("company_name", "default_timezone", "updated_at")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "audience", "is_active", "starts_at", "ends_at")
    list_filter = ("audience", "is_active")
    search_fields = ("title", "body")
