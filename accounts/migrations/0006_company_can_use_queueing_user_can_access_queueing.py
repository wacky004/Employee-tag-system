from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_company_user_company"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="can_use_queueing",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="can_access_queueing",
            field=models.BooleanField(default=False),
        ),
    ]
