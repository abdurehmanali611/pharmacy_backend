from django.db import models

class Medicine(models.Model):
    pharmacy_tin = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=64, blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=0)
    expiry_date = models.DateField(null=True, blank=True)
    description = models.TextField()
    supplier_name = models.CharField(max_length=255)
    supplier_phone = models.CharField(max_length=50)
    supplier_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.name} ({self.pharmacy_tin})"
