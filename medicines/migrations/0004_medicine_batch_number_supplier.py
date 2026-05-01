from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("suppliers", "0001_initial"),
        ("medicines", "0003_medicine_category_medicine_expiry_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="medicine",
            name="batch_number",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="medicine",
            name="supplier",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="medicines",
                to="suppliers.supplier",
            ),
        ),
    ]
