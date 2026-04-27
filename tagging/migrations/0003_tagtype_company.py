from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_company_can_use_queueing_user_can_access_queueing"),
        ("tagging", "0002_alter_taglog_table_alter_tagtype_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="tagtype",
            name="company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name="tag_types",
                to="accounts.company",
            ),
        ),
    ]
