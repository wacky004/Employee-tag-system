from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("queueing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="queueservice",
            name="show_in_ticket_generation",
            field=models.BooleanField(default=True),
        ),
    ]
