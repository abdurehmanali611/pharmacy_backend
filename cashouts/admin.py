from django.contrib import admin

from .models import Cashout


@admin.register(Cashout)
class CashoutAdmin(admin.ModelAdmin):
    list_display = ("amount", "reason", "pharmacy_tin", "created_at")
    search_fields = ("reason", "pharmacy_tin")

