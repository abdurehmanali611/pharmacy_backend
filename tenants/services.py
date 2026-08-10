from django.utils import timezone

from .models import TenantAccount


def ensure_tenant_account(*, pharmacy_tin: str, pharmacy_name: str = "", logo_url: str = "") -> TenantAccount | None:
    tin = (pharmacy_tin or "").strip()
    if not tin:
        return None

    tenant, created = TenantAccount.objects.get_or_create(
        pharmacy_tin=tin,
        defaults={
            "pharmacy_name": (pharmacy_name or "").strip(),
            "logo_url": (logo_url or "").strip(),
            "account_status": TenantAccount.STATUS_ACTIVE,
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
        if dirty:
            tenant.save(update_fields=["pharmacy_name", "logo_url", "updated_at"])
    return tenant


def set_tenant_status(tenant: TenantAccount, status: str, reason: str = "") -> TenantAccount:
    tenant.account_status = status
    tenant.status_reason = reason or ""
    tenant.status_changed_at = timezone.now()
    tenant.save(update_fields=["account_status", "status_reason", "status_changed_at", "updated_at"])
    return tenant
