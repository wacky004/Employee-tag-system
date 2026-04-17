from django.contrib.auth.models import AbstractUser
from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    can_use_tagging = models.BooleanField(default=True)
    can_use_inventory = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "companies"
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name

    @staticmethod
    def normalize_identifier(value):
        return "".join(character for character in (value or "").lower() if character.isalnum())

    def matches_identifier(self, value):
        normalized_value = self.normalize_identifier(value)
        return normalized_value in {
            self.normalize_identifier(self.code),
            self.normalize_identifier(self.name),
        }

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sync_user_module_access()

    def sync_user_module_access(self):
        updates = {}
        if not self.can_use_tagging:
            updates["can_access_tagging"] = False
        if not self.can_use_inventory:
            updates["can_access_inventory"] = False
        if updates:
            self.users.update(**updates)


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
    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    limit_to_enabled_modules = models.BooleanField(default=False)
    can_access_tagging = models.BooleanField(default=False)
    can_access_inventory = models.BooleanField(default=False)
    email = models.EmailField(unique=True)

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.get_full_name() or self.username

    def is_platform_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN and self.company_id is None and not self.limit_to_enabled_modules

    def has_full_module_access(self):
        return self.is_platform_super_admin()

    def can_manage_module_access(self):
        return self.has_full_module_access()

    def can_manage_companies(self):
        return self.has_full_module_access()

    def matches_organization(self, organization_value):
        normalized_value = Company.normalize_identifier(organization_value)
        if self.company_id:
            return self.company.matches_identifier(organization_value)
        return normalized_value in {"aquiso", "platform"}

    def company_allows_module(self, module_name):
        if self.company_id is None:
            return True
        if not self.company.is_active:
            return False
        module_map = {
            "tagging": self.company.can_use_tagging,
            "inventory": self.company.can_use_inventory,
        }
        return module_map.get(module_name, False)

    def has_tagging_module_access(self):
        if not self.company_allows_module("tagging"):
            return False
        if self.role == self.Role.SUPER_ADMIN:
            return self.has_full_module_access() or self.can_access_tagging
        return self.role == self.Role.EMPLOYEE or self.can_access_tagging

    def has_inventory_module_access(self):
        if not self.company_allows_module("inventory"):
            return False
        if self.role == self.Role.SUPER_ADMIN:
            return self.has_full_module_access() or self.can_access_inventory
        return self.role == self.Role.ADMIN or self.can_access_inventory
