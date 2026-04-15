from django.conf import settings
from django.db import models
from django.utils import timezone


class InventoryUser(models.Model):
    full_name = models.CharField(max_length=150)
    employee_code = models.CharField(max_length=30, unique=True)
    department_name = models.CharField(max_length=100, blank=True)
    team_name = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    is_supervisor = models.BooleanField(default=False)
    supervisor = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_members",
        limit_choices_to={"is_supervisor": True},
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_users"
        ordering = ["full_name", "employee_code"]

    def __str__(self):
        return f"{self.full_name} ({self.employee_code})"


class Equipment(models.Model):
    class Status(models.TextChoices):
        BRAND_NEW = "BRAND_NEW", "Brand New"
        USED = "USED", "Used"
        UNUSED = "UNUSED", "Unused"
        DEFECTIVE = "DEFECTIVE", "Defective"
        TO_BE_CHECKED = "TO_BE_CHECKED", "To Be Checked"

    asset_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=100, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNUSED,
    )
    current_holder = models.ForeignKey(
        InventoryUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_equipment",
    )
    last_assigned_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
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
    holder = models.ForeignKey(
        InventoryUser,
        on_delete=models.CASCADE,
        related_name="equipment_history",
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
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "equipment_assignments"
        ordering = ["-assigned_at", "-id"]

    def __str__(self):
        return f"{self.equipment} -> {self.holder}"
