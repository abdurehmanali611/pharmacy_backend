from django.contrib import admin

from .models import (
    ApprovalRequiredMedicine,
    PendingSale,
    PendingSaleLine,
    QuantitySaleRule,
)


class PendingSaleLineInline(admin.TabularInline):
    model = PendingSaleLine
    extra = 0


@admin.register(QuantitySaleRule)
class QuantitySaleRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "pharmacy_tin", "medicine", "threshold", "final", "created_at")
    list_filter = ("pharmacy_tin",)


@admin.register(ApprovalRequiredMedicine)
class ApprovalRequiredMedicineAdmin(admin.ModelAdmin):
    list_display = ("id", "pharmacy_tin", "medicine", "created_at")
    list_filter = ("pharmacy_tin",)


@admin.register(PendingSale)
class PendingSaleAdmin(admin.ModelAdmin):
    list_display = ("id", "pharmacy_tin", "status", "created_by", "created_at")
    list_filter = ("status", "pharmacy_tin")
    inlines = [PendingSaleLineInline]
