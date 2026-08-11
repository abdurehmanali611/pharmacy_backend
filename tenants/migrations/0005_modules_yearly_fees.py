from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0004_unlock_existing_tenants"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantaccount",
            name="yearly_fee_etb",
            field=models.PositiveIntegerField(default=18000),
        ),
        migrations.AddField(
            model_name="tenantaccount",
            name="modules",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="tenantaccount",
            name="fees_manually_set",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="tenantpaymentsubmission",
            name="payment_kind",
            field=models.CharField(
                choices=[
                    ("setup", "Setup"),
                    ("quarterly", "Quarterly"),
                    ("yearly", "Yearly"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
    ]
