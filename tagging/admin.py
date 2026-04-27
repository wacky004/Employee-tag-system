from django.contrib import admin

from .models import TagLog, TagType


@admin.register(TagType)
class TagTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "company", "category", "direction", "default_allowed_minutes", "is_active")
    list_filter = ("company", "category", "direction", "is_active")
    search_fields = ("code", "name", "company__name", "company__code")


@admin.register(TagLog)
class TagLogAdmin(admin.ModelAdmin):
    list_display = ("employee", "tag_type", "work_date", "timestamp", "source")
    list_filter = ("tag_type", "source", "work_date")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name", "notes")
