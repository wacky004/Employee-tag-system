from django.contrib import admin

from .models import Equipment, EquipmentAssignment, InventoryUser


@admin.register(InventoryUser)
class InventoryUserAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "full_name", "is_supervisor", "supervisor", "department_name", "team_name")
    search_fields = ("employee_code", "full_name", "job_title", "department_name", "team_name")
    list_filter = ("is_supervisor", "is_active", "department_name", "team_name")


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ("asset_code", "name", "status", "current_holder", "category", "brand", "last_assigned_at")
    search_fields = ("asset_code", "name", "serial_number", "brand", "model_number")
    list_filter = ("status", "category", "brand")


@admin.register(EquipmentAssignment)
class EquipmentAssignmentAdmin(admin.ModelAdmin):
    list_display = ("equipment", "holder", "assigned_by", "assigned_at", "returned_at")
    search_fields = ("equipment__asset_code", "equipment__name", "holder__employee_code", "holder__full_name")
    list_filter = ("assigned_at", "returned_at")
