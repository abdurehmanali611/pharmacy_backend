from django.contrib import admin

from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("supplier_name", "supplier_phone", "supplier_email", "pharmacy_tin")
    search_fields = ("supplier_name", "supplier_phone", "supplier_email", "pharmacy_tin")

