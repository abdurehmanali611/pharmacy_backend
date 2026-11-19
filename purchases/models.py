from django.conf import settings
from django.db import models

from medicines.models import Medicine

class Purchase(models.Model):
    pharmacy_tin = models.CharField(max_length=50)
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.SET_NULL,
        related_name="sales",
        null=True,
        blank=True,
    )
    medicine_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    # What rules did to this sale: who got a discount, the pre-discount price, and why it was held.
    customer_name = models.CharField(max_length=255, blank=True, default="")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    list_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rule_trigger = models.CharField(max_length=32, blank=True, default="none")
    # Who rang up the sale; the name is kept so reports survive deleting an agent account.
    sold_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_made",
    )
    sold_by_name = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.medicine_name} ({self.pharmacy_tin})"