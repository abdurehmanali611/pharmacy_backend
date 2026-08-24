from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0006_subscriptionpricingrule_tenantfeedbackmessage_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalesAgent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(max_length=255)),
                ("phone", models.CharField(blank=True, default="", max_length=64)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("city", models.CharField(blank=True, default="", max_length=128)),
                ("notes", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["display_name"],
            },
        ),
        migrations.AddField(
            model_name="tenantaccount",
            name="sales_agent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tenants",
                to="tenants.salesagent",
            ),
        ),
    ]
