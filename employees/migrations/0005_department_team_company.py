from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_company_user_company"),
        ("employees", "0004_employeeprofile_schedule_end_time_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="department",
            name="company",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="departments", to="accounts.company"),
        ),
        migrations.AddField(
            model_name="team",
            name="company",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="teams", to="accounts.company"),
        ),
    ]
