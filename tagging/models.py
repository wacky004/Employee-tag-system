from django.conf import settings
from django.db import models


class TagType(models.Model):
    class Category(models.TextChoices):
        SHIFT = "SHIFT", "Shift"
        LUNCH = "LUNCH", "Lunch"
        BREAK = "BREAK", "Break"
        BIO = "BIO", "Bio"

    class Direction(models.TextChoices):
        IN = "IN", "In"
        OUT = "OUT", "Out"

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=50)
    category = models.CharField(max_length=20, choices=Category.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    default_allowed_minutes = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class TagLog(models.Model):
    class Source(models.TextChoices):
        WEB = "WEB", "Web"
        ADMIN = "ADMIN", "Admin"
        CORRECTION = "CORRECTION", "Correction"
        SYSTEM = "SYSTEM", "System"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tag_logs",
    )
    tag_type = models.ForeignKey(
        TagType,
        on_delete=models.PROTECT,
        related_name="logs",
    )
    work_date = models.DateField()
    timestamp = models.DateTimeField()
    work_mode = models.CharField(max_length=10, blank=True)
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.WEB,
    )
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tag_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp", "-id"]

    def __str__(self):
        return f"{self.employee} - {self.tag_type.code} @ {self.timestamp}"
