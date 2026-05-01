from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("suppliers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pharmacy_tin", models.CharField(max_length=50)),
                ("invoice_number", models.CharField(max_length=255)),
                ("invoice_date", models.DateField()),
                ("invoice_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("invoice_status", models.CharField(choices=[("paid", "Paid"), ("unpaid", "Unpaid")], max_length=20)),
                ("invoice_type", models.CharField(choices=[("purchase", "Purchase"), ("sale", "Sale")], max_length=20)),
                ("invoice_payment_method", models.CharField(choices=[("Cash", "Cash"), ("Bank", "Bank"), ("Credit", "Credit")], max_length=20)),
                ("invoice_image", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "supplier",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invoices",
                        to="suppliers.supplier",
                    ),
                ),
            ],
            options={
                "ordering": ["-invoice_date", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                fields=("pharmacy_tin", "invoice_number"),
                name="unique_invoice_number_per_pharmacy",
            ),
        ),
    ]

