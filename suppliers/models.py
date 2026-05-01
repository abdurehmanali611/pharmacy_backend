from django.db import models


class Supplier(models.Model):
    pharmacy_tin = models.CharField(max_length=50)
    supplier_name = models.CharField(max_length=255)
    supplier_phone = models.CharField(max_length=50)
    supplier_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["supplier_name", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["pharmacy_tin", "supplier_name"],
                name="unique_supplier_name_per_pharmacy",
            )
        ]

    def __str__(self):
        return f"{self.supplier_name} ({self.pharmacy_tin})"

