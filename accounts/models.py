from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "roles"
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        ADMIN = "ADMIN", "Admin"
        EMPLOYEE = "EMPLOYEE", "Employee"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
    )
    role_record = models.ForeignKey(
        "accounts.Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    email = models.EmailField(unique=True)

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.get_full_name() or self.username
