from django.contrib import admin

from .models import TenantAccount, TenantPaymentSubmission


@admin.register(TenantAccount)
class TenantAccountAdmin(admin.ModelAdmin):
    list_display = (
        "pharmacy_tin",
        "pharmacy_name",
        "account_status",
        "setup_fee_approved",
        "subscription_paid_until",
        "created_at",
    )
    list_filter = ("account_status", "setup_fee_approved", "billing_hold")
    search_fields = ("pharmacy_tin", "pharmacy_name")


@admin.register(TenantPaymentSubmission)
class TenantPaymentSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "pharmacy_tin",
        "payment_kind",
        "amount_etb",
        "status",
        "transaction_ref",
        "submitted_at",
    )
    list_filter = ("payment_kind", "status")
    search_fields = ("pharmacy_tin", "transaction_ref")
