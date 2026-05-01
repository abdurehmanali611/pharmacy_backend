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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.name} ({self.pharmacy_tin})"
