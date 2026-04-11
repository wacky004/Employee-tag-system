from django.conf import settings
from django.db import models

from tagging.models import TagType


class AttendanceSession(models.Model):
    class Status(models.TextChoices):
        OFF_DUTY = "OFF_DUTY", "Off Duty"
        WORKING = "WORKING", "Working"
        LUNCH = "LUNCH", "Lunch"
        BREAK = "BREAK", "Break"
        BIO = "BIO", "Bio"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_sessions",
    )
    work_date = models.DateField()
    first_time_in = models.DateTimeField(null=True, blank=True)
    last_time_out = models.DateTimeField(null=True, blank=True)
    current_status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OFF_DUTY,
    )
    work_mode = models.CharField(max_length=10, blank=True)
    timezone_at_log = models.CharField(max_length=64, default="Asia/Manila")
    total_work_minutes = models.PositiveIntegerField(default=0)
    total_late_minutes = models.PositiveIntegerField(default=0)
    is_late = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "attendance_sessions"
        unique_together = ("employee", "work_date")
        ordering = ["-work_date", "employee_id"]

    def __str__(self):
        return f"{self.employee} - {self.work_date}"


class OverbreakRecord(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "RESOLVED", "Resolved"
        WAIVED = "WAIVED", "Waived"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="overbreak_records",
    )
    attendance_session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name="overbreak_records",
    )
    tag_type = models.ForeignKey(
        TagType,
        on_delete=models.PROTECT,
        related_name="overbreak_records",
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    allowed_minutes = models.PositiveIntegerField()
    actual_minutes = models.PositiveIntegerField()
    excess_minutes = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_overbreaks",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "overbreak_records"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} - {self.excess_minutes} mins over"


class CorrectionRequest(models.Model):
    class RequestType(models.TextChoices):
        MISSING_TAG = "MISSING_TAG", "Missing Tag"
        EDIT_LOG = "EDIT_LOG", "Edit Log"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="correction_requests",
    )
    attendance_session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="correction_requests",
    )
    request_type = models.CharField(max_length=20, choices=RequestType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    target_work_date = models.DateField()
    details = models.TextField()
    resolution_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_corrections",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "correction_requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} - {self.request_type} - {self.status}"
