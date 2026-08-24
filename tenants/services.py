from django.utils import timezone

from .billing import catalog_default_fees
from .models import TenantAccount


def ensure_tenant_account(
    *,
    pharmacy_tin: str,
    pharmacy_name: str = "",
    logo_url: str = "",
    sales_agent=None,
) -> TenantAccount | None:
    tin = (pharmacy_tin or "").strip()
    if not tin:
        return None

    fees = catalog_default_fees()
    tenant, created = TenantAccount.objects.get_or_create(
        pharmacy_tin=tin,
        defaults={
            "pharmacy_name": (pharmacy_name or "").strip(),
            "logo_url": (logo_url or "").strip(),
            "account_status": TenantAccount.STATUS_ACTIVE,
            "setup_fee_etb": fees["setup_fee_etb"],
            "quarterly_fee_etb": fees["quarterly_fee_etb"],
            "yearly_fee_etb": fees.get("yearly_fee_etb") or 0,
            "sales_agent": sales_agent,
            "setup_fee_approved": False,
            "subscription_payment_approved": False,
        },
    )
    if not created:
        dirty = False
        name = (pharmacy_name or "").strip()
        logo = (logo_url or "").strip()
        if name and tenant.pharmacy_name != name:
            tenant.pharmacy_name = name
            dirty = True
        if logo and tenant.logo_url != logo:
            tenant.logo_url = logo
            dirty = True
        # Keep unconfigured new tenants aligned with the live catalog
        # until Apex manually overrides fees on the tenant.
        if not tenant.fees_manually_set and not tenant.setup_fee_approved:
            if tenant.setup_fee_etb != fees["setup_fee_etb"]:
                tenant.setup_fee_etb = fees["setup_fee_etb"]
                dirty = True
            if tenant.quarterly_fee_etb != fees["quarterly_fee_etb"]:
                tenant.quarterly_fee_etb = fees["quarterly_fee_etb"]
                dirty = True
        if dirty:
            tenant.save()
    return tenant


def set_tenant_status(tenant: TenantAccount, status: str, reason: str = "") -> TenantAccount:
    tenant.account_status = status
    tenant.status_reason = reason or ""
    tenant.status_changed_at = timezone.now()
    tenant.save(update_fields=["account_status", "status_reason", "status_changed_at", "updated_at"])
    return tenant
