from django.contrib import admin

# Register your models here.

from .models import StockLoss


@admin.register(StockLoss)
class StockLossAdmin(admin.ModelAdmin):
    list_display = ("id", "pharmacy_tin", "medicine_name", "kind", "quantity", "created_at")
    list_filter = ("pharmacy_tin", "kind")
