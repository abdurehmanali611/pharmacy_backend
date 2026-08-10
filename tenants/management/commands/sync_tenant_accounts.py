from django.core.management.base import BaseCommand

from tenants.services import ensure_tenant_account
from user.models import UserProfile


class Command(BaseCommand):
    help = "Backfill TenantAccount rows for existing manager pharmacy TINs."

    def handle(self, *args, **options):
        managers = UserProfile.objects.exclude(pharmacy_tin="").filter(role__iexact="Manager")
        created = 0
        for profile in managers:
            before = profile.pharmacy_tin
            tenant = ensure_tenant_account(
                pharmacy_tin=profile.pharmacy_tin,
                pharmacy_name=profile.pharmacy_name,
                logo_url=profile.logoUrl,
            )
            if tenant and tenant.created_at == tenant.updated_at:
                created += 1
            self.stdout.write(f"Ensured tenant for {before}")
        self.stdout.write(self.style.SUCCESS(f"Done. Processed {managers.count()} manager profiles."))
