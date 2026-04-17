from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("queueing", "0002_queueservice_show_in_ticket_generation"),
    ]

    operations = [
        migrations.AddField(
            model_name="queuedisplayscreen",
            name="refresh_interval_seconds",
            field=models.PositiveIntegerField(default=15),
        ),
        migrations.AddField(
            model_name="queuedisplayscreen",
            name="slug",
            field=models.SlugField(default="", max_length=150, unique=True),
            preserve_default=False,
        ),
    ]
