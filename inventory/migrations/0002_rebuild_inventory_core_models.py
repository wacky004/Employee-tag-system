# Generated manually to replace the initial placeholder inventory schema

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Supervisor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=150)),
                ("employee_code", models.CharField(max_length=30, unique=True)),
                ("department", models.CharField(blank=True, max_length=100)),
                ("job_title", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "inventory_supervisors",
                "ordering": ["full_name", "employee_code"],
            },
        ),
        migrations.CreateModel(
            name="Employee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=150)),
                ("employee_code", models.CharField(max_length=30, unique=True)),
                ("department", models.CharField(blank=True, max_length=100)),
                ("team_name", models.CharField(blank=True, max_length=100)),
                ("job_title", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "supervisor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="employees",
                        to="inventory.supervisor",
                    ),
                ),
            ],
            options={
                "db_table": "inventory_employees",
                "ordering": ["full_name", "employee_code"],
            },
        ),
        migrations.CreateModel(
            name="EquipmentCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("code", models.CharField(max_length=30, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name_plural": "Equipment categories",
                "db_table": "inventory_equipment_categories",
                "ordering": ["name"],
            },
        ),
        migrations.RemoveField(
            model_name="equipment",
            name="current_holder",
        ),
        migrations.DeleteModel(
            name="EquipmentAssignment",
        ),
        migrations.DeleteModel(
            name="InventoryUser",
        ),
        migrations.RemoveField(
            model_name="equipment",
            name="category",
        ),
        migrations.RemoveField(
            model_name="equipment",
            name="model_number",
        ),
        migrations.AddField(
            model_name="equipment",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="equipment",
                to="inventory.equipmentcategory",
            ),
        ),
        migrations.AddField(
            model_name="equipment",
            name="current_employee",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="current_equipment",
                to="inventory.employee",
            ),
        ),
        migrations.AddField(
            model_name="equipment",
            name="model",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name="equipment",
            name="serial_number",
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="equipment",
            name="status",
            field=models.CharField(
                choices=[
                    ("BRANDNEW", "Brand New"),
                    ("USED", "Used"),
                    ("UNUSED", "Unused"),
                    ("DEFECTIVE", "Defective"),
                    ("TO_BE_CHECKED", "To Be Checked"),
                ],
                default="UNUSED",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="EquipmentAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assigned_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("remarks", models.TextField(blank=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="inventory_assignments_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="equipment_assignments",
                        to="inventory.employee",
                    ),
                ),
                (
                    "equipment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="inventory.equipment",
                    ),
                ),
            ],
            options={
                "db_table": "inventory_equipment_assignments",
                "ordering": ["-assigned_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="EquipmentHistoryLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("ASSIGNED", "Assigned"),
                            ("RETURNED", "Returned"),
                            ("STATUS_CHANGED", "Status Changed"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status_snapshot",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("BRANDNEW", "Brand New"),
                            ("USED", "Used"),
                            ("UNUSED", "Unused"),
                            ("DEFECTIVE", "Defective"),
                            ("TO_BE_CHECKED", "To Be Checked"),
                        ],
                        max_length=20,
                    ),
                ),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "assignment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="history_logs",
                        to="inventory.equipmentassignment",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="equipment_history_logs",
                        to="inventory.employee",
                    ),
                ),
                (
                    "equipment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history_logs",
                        to="inventory.equipment",
                    ),
                ),
            ],
            options={
                "db_table": "inventory_equipment_history_logs",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
