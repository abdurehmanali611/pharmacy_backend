from django.db import models

from suppliers.models import Supplier


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("paid", "Paid"),
        ("unpaid", "Unpaid"),
    ]
    TYPE_CHOICES = [
        ("purchase", "Purchase"),
        ("sale", "Sale"),
    ]
    PAYMENT_METHOD_CHOICES = [
        ("Cash", "Cash"),
        ("Bank", "Bank"),
        ("Credit", "Credit"),
    ]

    pharmacy_tin = models.CharField(max_length=50)
    supplier = models.ForeignKey(
        Supplier,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=255)
    invoice_date = models.DateField()
    invoice_amount = models.DecimalField(max_digits=10, decimal_places=2)
    invoice_status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    invoice_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    invoice_payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    invoice_image = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invoice_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["pharmacy_tin", "invoice_number"],
                name="unique_invoice_number_per_pharmacy",
            )
        ]

    def __str__(self):
        return f"{self.invoice_number} ({self.pharmacy_tin})"

