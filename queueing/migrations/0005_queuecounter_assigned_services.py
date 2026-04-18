from django.db import migrations, models


def copy_assigned_service_to_many_to_many(apps, schema_editor):
    QueueCounter = apps.get_model("queueing", "QueueCounter")
    for counter in QueueCounter.objects.exclude(assigned_service__isnull=True):
        counter.assigned_services.add(counter.assigned_service_id)


class Migration(migrations.Migration):

    dependencies = [
        ("queueing", "0004_queuehistorylog_status_snapshot_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="queuecounter",
            name="assigned_services",
            field=models.ManyToManyField(blank=True, related_name="counters", to="queueing.queueservice"),
        ),
        migrations.RunPython(copy_assigned_service_to_many_to_many, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="queuecounter",
            name="assigned_service",
        ),
    ]
