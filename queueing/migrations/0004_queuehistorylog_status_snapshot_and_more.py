from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("queueing", "0003_queuedisplayscreen_refresh_interval_seconds_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="queuehistorylog",
            name="action",
            field=models.CharField(
                choices=[
                    ("CREATED", "Created"),
                    ("CALLED", "Called"),
                    ("SERVING", "Serving"),
                    ("COMPLETED", "Completed"),
                    ("SKIPPED", "Skipped"),
                    ("CANCELLED", "Cancelled"),
                    ("RECALL", "Recalled"),
                    ("REASSIGNED", "Reassigned"),
                    ("MANUAL_EDITED", "Manually Edited"),
                    ("SERVICE_UPDATED", "Service Updated"),
                    ("COUNTER_UPDATED", "Counter Updated"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="queuehistorylog",
            name="ticket",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="history_logs",
                to="queueing.queueticket",
            ),
        ),
        migrations.AddField(
            model_name="queuehistorylog",
            name="status_snapshot",
            field=models.CharField(
                blank=True,
                choices=[
                    ("WAITING", "Waiting"),
                    ("CALLED", "Called"),
                    ("SERVING", "Serving"),
                    ("COMPLETED", "Completed"),
                    ("SKIPPED", "Skipped"),
                    ("CANCELLED", "Cancelled"),
                ],
                max_length=20,
            ),
        ),
    ]
