from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_rebuild_inventory_core_models"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("EQUIPMENT_CREATED", "Equipment Created"),
                            ("EQUIPMENT_UPDATED", "Equipment Updated"),
                            ("EQUIPMENT_ASSIGNED", "Equipment Assigned"),
                            ("EQUIPMENT_RETURNED", "Equipment Returned"),
                            ("EMPLOYEE_CREATED", "Employee Created"),
                            ("SUPERVISOR_CREATED", "Supervisor Created"),
                        ],
                        max_length=30,
                    ),
                ),
                ("target_type", models.CharField(max_length=50)),
                ("target_id", models.PositiveIntegerField()),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("notes", models.TextField(blank=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="inventory_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "inventory_audit_logs",
                "ordering": ["-timestamp", "-id"],
            },
        ),
    ]
