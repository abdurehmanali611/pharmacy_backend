import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("medicines", "0004_medicine_batch_number_supplier"),
        ("purchases", "0002_purchase_cost_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchase",
            name="medicine",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sales",
                to="medicines.medicine",
            ),
        ),
    ]
