from django.contrib import admin

from .models import EmployeeProfile, Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "lead", "created_at")
    search_fields = ("code", "name")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "user", "team", "default_work_mode", "is_active")
    list_filter = ("default_work_mode", "is_active", "team")
    search_fields = ("employee_code", "user__username", "user__first_name", "user__last_name")
