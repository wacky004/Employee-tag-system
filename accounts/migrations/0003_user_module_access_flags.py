from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_role_alter_user_options_alter_user_table_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="can_access_inventory",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="can_access_tagging",
            field=models.BooleanField(default=False),
        ),
    ]
