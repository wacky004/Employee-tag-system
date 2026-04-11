from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "target_model", "target_id", "actor", "created_at")
    list_filter = ("action", "target_model")
    search_fields = ("target_id", "description", "actor__username")
