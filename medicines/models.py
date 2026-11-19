from django.conf import settings
from django.db import models

from suppliers.models import Supplier

class Medicine(models.Model):
    pharmacy_tin = models.CharField(max_length=50)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        related_name="medicines",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=64, blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=0)
    batch_number = models.CharField(max_length=255, blank=True, default="")
    expiry_date = models.DateField(null=True, blank=True)
    description = models.TextField()
    image_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.name} ({self.pharmacy_tin})"


class StockLoss(models.Model):
    """Audit record for stock removed because it was damaged or wasted."""

    KIND_DAMAGED = "damaged"
    KIND_WASTED = "wasted"
    KIND_CHOICES = [
        (KIND_DAMAGED, "Damaged"),
        (KIND_WASTED, "Wasted"),
    ]

    pharmacy_tin = models.CharField(max_length=50, db_index=True)
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.SET_NULL,
        related_name="stock_losses",
        null=True,
        blank=True,
    )
    medicine_name = models.CharField(max_length=255)
    batch_number = models.CharField(max_length=255, blank=True, default="")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    quantity = models.PositiveIntegerField()
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    note = models.CharField(max_length=500, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_losses_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} {self.medicine_name} x{self.quantity} ({self.pharmacy_tin})"
