from django.contrib import admin

from .models import Employee, Equipment, EquipmentAssignment, EquipmentCategory, EquipmentHistoryLog, Supervisor


@admin.register(Supervisor)
class SupervisorAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "full_name", "department", "job_title", "is_active")
    search_fields = ("employee_code", "full_name", "department", "job_title")
    list_filter = ("is_active", "department")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "full_name", "supervisor", "department", "team_name", "is_active")
    search_fields = ("employee_code", "full_name", "department", "team_name", "job_title")
    list_filter = ("is_active", "department", "team_name")


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ("asset_code", "name", "category", "status", "current_employee", "last_assigned_at")
    search_fields = ("asset_code", "name", "serial_number", "brand", "model")
    list_filter = ("status", "category")


@admin.register(EquipmentAssignment)
class EquipmentAssignmentAdmin(admin.ModelAdmin):
    list_display = ("equipment", "employee", "assigned_by", "assigned_at", "returned_at")
    search_fields = ("equipment__asset_code", "equipment__name", "employee__employee_code", "employee__full_name")
    list_filter = ("assigned_at", "returned_at")


@admin.register(EquipmentHistoryLog)
class EquipmentHistoryLogAdmin(admin.ModelAdmin):
    list_display = ("equipment", "employee", "action", "status_snapshot", "created_at")
    search_fields = ("equipment__asset_code", "equipment__name", "employee__employee_code", "employee__full_name")
    list_filter = ("action", "status_snapshot", "created_at")
