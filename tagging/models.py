from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


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
    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tag_types",
    )
    name = models.CharField(max_length=50)
    category = models.CharField(max_length=20, choices=Category.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    default_allowed_minutes = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "tag_types"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name

    @property
    def scope_label(self):
        return self.company.name if self.company_id else "Platform Default"

    def clean(self):
        super().clean()
        if not self.is_active:
            return

        conflict = TagType.objects.filter(
            company=self.company,
            category=self.category,
            direction=self.direction,
            is_active=True,
        ).exclude(pk=self.pk)
        if conflict.exists():
            scope = self.company.name if self.company_id else "the platform defaults"
            raise ValidationError(
                {
                    "is_active": (
                        f"An active {self.get_category_display()} {self.get_direction_display()} tag "
                        f"already exists for {scope}."
                    )
                }
            )

    @classmethod
    def active_for_company(cls, company=None):
        queryset = cls.objects.filter(is_active=True)
        if company is None:
            return queryset.filter(company__isnull=True)
        return queryset.filter(Q(company__isnull=True) | Q(company=company))

    @classmethod
    def effective_map_for_company(cls, company=None):
        tag_map = {
            (tag.category, tag.direction): tag
            for tag in cls.objects.filter(company__isnull=True, is_active=True).order_by("sort_order", "id")
        }
        if company is not None:
            tag_map.update(
                {
                    (tag.category, tag.direction): tag
                    for tag in cls.objects.filter(company=company, is_active=True).order_by("sort_order", "id")
                }
            )
        return tag_map

    @classmethod
    def effective_for_company(cls, company=None):
        return sorted(
            cls.effective_map_for_company(company).values(),
            key=lambda tag: (tag.sort_order, tag.id),
        )


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
        db_table = "tag_logs"
        ordering = ["-timestamp", "-id"]

    def __str__(self):
        return f"{self.employee} - {self.tag_type.code} @ {self.timestamp}"
