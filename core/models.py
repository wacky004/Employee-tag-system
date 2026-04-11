from django.db import models


class SystemSetting(models.Model):
    company_name = models.CharField(max_length=150, default="Attendance System")
    default_timezone = models.CharField(max_length=64, default="Asia/Manila")
    lunch_minutes_allowed = models.PositiveIntegerField(default=60)
    break_minutes_allowed = models.PositiveIntegerField(default=15)
    bio_minutes_allowed = models.PositiveIntegerField(default=10)
    late_after_time = models.TimeField(null=True, blank=True)
    overbreak_grace_minutes = models.PositiveIntegerField(default=0)
    allow_employee_log_edit = models.BooleanField(default=False)
    allow_admin_log_edit = models.BooleanField(default=True)
    allow_duplicate_tags = models.BooleanField(default=False)
    require_work_mode_on_time_in = models.BooleanField(default=True)
    allow_multiple_tag_clicks = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "System Settings"
