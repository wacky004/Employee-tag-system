from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0006_company_can_use_queueing_user_can_access_queueing"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QueueService",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("code", models.CharField(max_length=20)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("max_queue_limit", models.PositiveIntegerField(default=100)),
                ("current_queue_number", models.PositiveIntegerField(default=0)),
                ("allow_priority", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="queue_services", to="accounts.company"),
                ),
            ],
            options={
                "db_table": "queueing_services",
                "ordering": ["name", "code"],
            },
        ),
        migrations.CreateModel(
            name="QueueCounter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assigned_service",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="counters", to="queueing.queueservice"),
                ),
                (
                    "company",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="queue_counters", to="accounts.company"),
                ),
            ],
            options={
                "db_table": "queueing_counters",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="QueueDisplayScreen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="queue_display_screens", to="accounts.company"),
                ),
                ("services", models.ManyToManyField(blank=True, related_name="display_screens", to="queueing.queueservice")),
            ],
            options={
                "db_table": "queueing_display_screens",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="QueueSystemSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "queue_reset_policy",
                    models.CharField(
                        choices=[("DAILY", "Daily"), ("MANUAL", "Manual"), ("NEVER", "Never")],
                        default="DAILY",
                        max_length=20,
                    ),
                ),
                ("display_settings", models.JSONField(blank=True, default=dict)),
                ("default_max_queue_per_service", models.PositiveIntegerField(default=100)),
                ("announcement_settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="queue_system_setting", to="accounts.company"),
                ),
            ],
            options={
                "db_table": "queueing_system_settings",
                "ordering": ["company__name"],
            },
        ),
        migrations.CreateModel(
            name="QueueTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("queue_number", models.CharField(max_length=30)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("WAITING", "Waiting"),
                            ("CALLED", "Called"),
                            ("COMPLETED", "Completed"),
                            ("SKIPPED", "Skipped"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="WAITING",
                        max_length=20,
                    ),
                ),
                ("is_priority", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("called_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "assigned_counter",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tickets", to="queueing.queuecounter"),
                ),
                (
                    "company",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="queue_tickets", to="accounts.company"),
                ),
                (
                    "service",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tickets", to="queueing.queueservice"),
                ),
            ],
            options={
                "db_table": "queueing_tickets",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="QueueHistoryLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("CALLED", "Called"),
                            ("COMPLETED", "Completed"),
                            ("SKIPPED", "Skipped"),
                            ("CANCELLED", "Cancelled"),
                            ("REASSIGNED", "Reassigned"),
                        ],
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="queue_history_actions", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "company",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="queue_history_logs", to="accounts.company"),
                ),
                (
                    "counter",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="history_logs", to="queueing.queuecounter"),
                ),
                (
                    "service",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="history_logs", to="queueing.queueservice"),
                ),
                (
                    "ticket",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="history_logs", to="queueing.queueticket"),
                ),
            ],
            options={
                "db_table": "queueing_history_logs",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="queueservice",
            constraint=models.UniqueConstraint(fields=("company", "code"), name="queue_service_company_code_unique"),
        ),
        migrations.AddConstraint(
            model_name="queueservice",
            constraint=models.UniqueConstraint(fields=("company", "name"), name="queue_service_company_name_unique"),
        ),
        migrations.AddConstraint(
            model_name="queuecounter",
            constraint=models.UniqueConstraint(fields=("company", "name"), name="queue_counter_company_name_unique"),
        ),
        migrations.AddConstraint(
            model_name="queuedisplayscreen",
            constraint=models.UniqueConstraint(fields=("company", "name"), name="queue_display_screen_company_name_unique"),
        ),
        migrations.AddIndex(
            model_name="queueticket",
            index=models.Index(fields=["company", "status"], name="queue_ticket_comp_stat_idx"),
        ),
        migrations.AddIndex(
            model_name="queueticket",
            index=models.Index(fields=["company", "created_at"], name="queue_ticket_comp_created_idx"),
        ),
    ]
