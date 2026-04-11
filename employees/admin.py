from django.contrib import admin

from .models import Department, EmployeeProfile, Team


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "lead", "created_at")
    list_filter = ("department",)
    search_fields = ("code", "name")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "user", "department", "team", "default_work_mode", "is_active")
    list_filter = ("default_work_mode", "is_active", "department", "team")
    search_fields = ("employee_code", "user__username", "user__first_name", "user__last_name")
