from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pharmacy_tin", models.CharField(max_length=50)),
                ("supplier_name", models.CharField(max_length=255)),
                ("supplier_phone", models.CharField(max_length=50)),
                ("supplier_email", models.EmailField(blank=True, max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["supplier_name", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(
                fields=("pharmacy_tin", "supplier_name"),
                name="unique_supplier_name_per_pharmacy",
            ),
        ),
    ]

