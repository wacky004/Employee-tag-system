from django.conf import settings
from django.db import models

from accounts.models import Company


class QueueService(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="queue_services",
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    max_queue_limit = models.PositiveIntegerField(default=100)
    current_queue_number = models.PositiveIntegerField(default=0)
    allow_priority = models.BooleanField(default=False)
    show_in_ticket_generation = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "queueing_services"
        ordering = ["name", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="queue_service_company_code_unique"),
            models.UniqueConstraint(fields=["company", "name"], name="queue_service_company_name_unique"),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class QueueCounter(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="queue_counters",
    )
    name = models.CharField(max_length=100)
    assigned_service = models.ForeignKey(
        QueueService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="counters",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "queueing_counters"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="queue_counter_company_name_unique"),
        ]

    def __str__(self):
        return self.name


class QueueTicket(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        CALLED = "CALLED", "Called"
        SERVING = "SERVING", "Serving"
        COMPLETED = "COMPLETED", "Completed"
        SKIPPED = "SKIPPED", "Skipped"
        CANCELLED = "CANCELLED", "Cancelled"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="queue_tickets",
    )
    queue_number = models.CharField(max_length=30)
    service = models.ForeignKey(
        QueueService,
        on_delete=models.CASCADE,
        related_name="tickets",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    assigned_counter = models.ForeignKey(
        QueueCounter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    is_priority = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "queueing_tickets"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["company", "status"], name="queue_ticket_comp_stat_idx"),
            models.Index(fields=["company", "created_at"], name="queue_ticket_comp_created_idx"),
        ]

    def __str__(self):
        return self.queue_number


class QueueHistoryLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        CALLED = "CALLED", "Called"
        SERVING = "SERVING", "Serving"
        COMPLETED = "COMPLETED", "Completed"
        SKIPPED = "SKIPPED", "Skipped"
        CANCELLED = "CANCELLED", "Cancelled"
        RECALL = "RECALL", "Recall"
        REASSIGNED = "REASSIGNED", "Reassigned"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="queue_history_logs",
    )
    ticket = models.ForeignKey(
        QueueTicket,
        on_delete=models.CASCADE,
        related_name="history_logs",
    )
    service = models.ForeignKey(
        QueueService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="history_logs",
    )
    counter = models.ForeignKey(
        QueueCounter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="history_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="queue_history_actions",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "queueing_history_logs"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.ticket.queue_number} - {self.action}"


class QueueDisplayScreen(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="queue_display_screens",
    )
    name = models.CharField(max_length=150)
    services = models.ManyToManyField(
        QueueService,
        blank=True,
        related_name="display_screens",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "queueing_display_screens"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="queue_display_screen_company_name_unique"),
        ]

    def __str__(self):
        return self.name


class QueueSystemSetting(models.Model):
    class QueueResetPolicy(models.TextChoices):
        DAILY = "DAILY", "Daily"
        MANUAL = "MANUAL", "Manual"
        NEVER = "NEVER", "Never"

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="queue_system_setting",
    )
    queue_reset_policy = models.CharField(
        max_length=20,
        choices=QueueResetPolicy.choices,
        default=QueueResetPolicy.DAILY,
    )
    display_settings = models.JSONField(default=dict, blank=True)
    default_max_queue_per_service = models.PositiveIntegerField(default=100)
    announcement_settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "queueing_system_settings"
        ordering = ["company__name"]

    def __str__(self):
        return f"Queue settings for {self.company.name}"
