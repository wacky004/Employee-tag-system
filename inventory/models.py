from django.conf import settings
from django.db import models
from django.utils import timezone


class Supervisor(models.Model):
    full_name = models.CharField(max_length=150)
    employee_code = models.CharField(max_length=30, unique=True)
    department = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_supervisors"
        ordering = ["full_name", "employee_code"]

    def __str__(self):
        return f"{self.full_name} ({self.employee_code})"


class Employee(models.Model):
    full_name = models.CharField(max_length=150)
    employee_code = models.CharField(max_length=30, unique=True)
    department = models.CharField(max_length=100, blank=True)
    team_name = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    supervisor = models.ForeignKey(
        Supervisor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_employees"
        ordering = ["full_name", "employee_code"]

    def __str__(self):
        return f"{self.full_name} ({self.employee_code})"


class EquipmentCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "inventory_equipment_categories"
        ordering = ["name"]
        verbose_name_plural = "Equipment categories"

    def __str__(self):
        return self.name


class Equipment(models.Model):
    class Status(models.TextChoices):
        BRANDNEW = "BRANDNEW", "Brand New"
        USED = "USED", "Used"
        UNUSED = "UNUSED", "Unused"
        DEFECTIVE = "DEFECTIVE", "Defective"
        TO_BE_CHECKED = "TO_BE_CHECKED", "To Be Checked"

    asset_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    category = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment",
    )
    brand = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNUSED,
    )
    notes = models.TextField(blank=True)
    current_employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_equipment",
    )
    last_assigned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_equipment"
        ordering = ["asset_code", "name"]

    def __str__(self):
        return f"{self.asset_code} - {self.name}"


class EquipmentAssignment(models.Model):
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="equipment_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_assignments_made",
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    returned_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        db_table = "inventory_equipment_assignments"
        ordering = ["-assigned_at", "-id"]

    def __str__(self):
        return f"{self.equipment} -> {self.employee}"


class EquipmentHistoryLog(models.Model):
    class Action(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        RETURNED = "RETURNED", "Returned"
        STATUS_CHANGED = "STATUS_CHANGED", "Status Changed"

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="history_logs",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_history_logs",
    )
    assignment = models.ForeignKey(
        EquipmentAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="history_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    status_snapshot = models.CharField(
        max_length=20,
        choices=Equipment.Status.choices,
        blank=True,
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_equipment_history_logs"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.equipment} - {self.action}"
