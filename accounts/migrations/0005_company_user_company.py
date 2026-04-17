from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_limit_to_enabled_modules"),
    ]

    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, unique=True)),
                ("code", models.CharField(max_length=50, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("can_use_tagging", models.BooleanField(default=True)),
                ("can_use_inventory", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "companies",
                "ordering": ["name"],
                "verbose_name_plural": "companies",
            },
        ),
        migrations.AddField(
            model_name="user",
            name="company",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="users", to="accounts.company"),
        ),
    ]
