from django.contrib import admin

from .models import TenantAccount


@admin.register(TenantAccount)
class TenantAccountAdmin(admin.ModelAdmin):
    list_display = ("pharmacy_tin", "pharmacy_name", "account_status", "created_at", "updated_at")
    list_filter = ("account_status",)
    search_fields = ("pharmacy_tin", "pharmacy_name")
