from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_company_user_company"),
        ("core", "0004_systemsetting_time_in_cooldown_hours"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsetting",
            name="company",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="system_settings", to="accounts.company"),
        ),
    ]
