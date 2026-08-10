from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def unlock_existing_tenants(apps, schema_editor):
    TenantAccount = apps.get_model("tenants", "TenantAccount")
    now = timezone.now()
    for tenant in TenantAccount.objects.all():
        if tenant.setup_fee_approved:
            continue
        tenant.setup_fee_approved = True
        if int(getattr(tenant, "quarterly_fee_etb", 0) or 0) > 0:
            tenant.subscription_payment_approved = True
            tenant.paid_quarters_count = max(int(tenant.paid_quarters_count or 0), 1)
            tenant.billing_started_at = tenant.billing_started_at or tenant.created_at or now
            tenant.subscription_paid_until = tenant.subscription_paid_until or (
                tenant.billing_started_at + timedelta(days=90)
            )
        tenant.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0003_billing_and_payments"),
    ]

    operations = [
        migrations.RunPython(unlock_existing_tenants, noop),
    ]
