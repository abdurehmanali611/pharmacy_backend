from django.contrib import admin

from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "invoice_date",
        "invoice_amount",
        "invoice_status",
        "invoice_type",
        "pharmacy_tin",
    )
    search_fields = ("invoice_number", "pharmacy_tin", "supplier__supplier_name")

