from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "departments"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams",
    )
    lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_teams",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "teams"
        ordering = ["name"]

    def __str__(self):
        return self.name


class EmployeeProfile(models.Model):
    class WorkMode(models.TextChoices):
        ONSITE = "ONSITE", "Onsite"
        WFH = "WFH", "Work From Home"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    employee_code = models.CharField(max_length=30, unique=True)
    job_title = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Manila")
    schedule_start_time = models.TimeField(null=True, blank=True)
    schedule_end_time = models.TimeField(null=True, blank=True)
    default_work_mode = models.CharField(
        max_length=10,
        choices=WorkMode.choices,
        default=WorkMode.ONSITE,
    )
    hire_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "employee_profiles"
        ordering = ["employee_code"]

    def __str__(self):
        return f"{self.employee_code} - {self.user}"
