from django.db import models


class SystemSetting(models.Model):
    company_name = models.CharField(max_length=150, default="Attendance System")
    default_timezone = models.CharField(max_length=64, default="Asia/Manila")
    required_work_minutes = models.PositiveIntegerField(default=480)
    lunch_minutes_allowed = models.PositiveIntegerField(default=60)
    break_minutes_allowed = models.PositiveIntegerField(default=15)
    bio_minutes_allowed = models.PositiveIntegerField(default=10)
    late_after_time = models.TimeField(null=True, blank=True)
    late_grace_minutes = models.PositiveIntegerField(default=0)
    overbreak_grace_minutes = models.PositiveIntegerField(default=0)
    allow_employee_log_edit = models.BooleanField(default=False)
    allow_admin_log_edit = models.BooleanField(default=True)
    allow_duplicate_tags = models.BooleanField(default=False)
    require_work_mode_on_time_in = models.BooleanField(default=True)
    allow_multiple_tag_clicks = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "system_settings"

    def __str__(self):
        return "System Settings"


class Announcement(models.Model):
    class Audience(models.TextChoices):
        ALL = "ALL", "All Users"
        EMPLOYEES = "EMPLOYEES", "Employees"
        ADMINS = "ADMINS", "Admins and Managers"

    title = models.CharField(max_length=150)
    body = models.TextField()
    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
        default=Audience.ALL,
    )
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "announcements"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
