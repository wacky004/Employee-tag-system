from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Severity(models.TextChoices):
        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        CRITICAL = "CRITICAL", "Critical"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_audit_logs",
    )
    action = models.CharField(max_length=100)
    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.INFO,
    )
    target_model = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} on {self.target_model}#{self.target_id}"
