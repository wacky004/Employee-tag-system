from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_module_access_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="limit_to_enabled_modules",
            field=models.BooleanField(default=False),
        ),
    ]
