from django.conf import settings
from django.db import models

from medicines.models import Medicine


class QuantitySaleRule(models.Model):
    """Rule 1: quantity band that holds a sale for manager approval."""

    pharmacy_tin = models.CharField(max_length=50, db_index=True)
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name="quantity_sale_rules",
    )
    threshold = models.PositiveIntegerField()
    final = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["pharmacy_tin", "medicine"],
                name="uniq_quantity_rule_medicine_per_pharmacy",
            ),
        ]

    def __str__(self):
        band = f">={self.threshold}" if self.final is None else f"{self.threshold}-{self.final}"
        return f"{self.medicine_id} {band} ({self.pharmacy_tin})"


class ApprovalRequiredMedicine(models.Model):
    """Rule 2: any sale of this medicine requires manager approval."""

    pharmacy_tin = models.CharField(max_length=50, db_index=True)
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name="approval_required_flags",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["pharmacy_tin", "medicine"],
                name="uniq_approval_required_medicine_per_pharmacy",
            ),
        ]

    def __str__(self):
        return f"{self.medicine_id} needs approval ({self.pharmacy_tin})"


class DiscountRule(models.Model):
    """Manager-defined discount for a named customer on selected medicines."""

    ROLE_HEALTH_PROFESSIONAL = "health_professional"
    ROLE_OTHER = "other"
    ROLE_CHOICES = [
        (ROLE_HEALTH_PROFESSIONAL, "Health professional"),
        (ROLE_OTHER, "Other"),
    ]

    pharmacy_tin = models.CharField(max_length=50, db_index=True)
    customer_name = models.CharField(max_length=255)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    specific_role = models.CharField(max_length=255, blank=True, default="")
    medicines = models.ManyToManyField(Medicine, related_name="discount_rules")
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["customer_name", "-created_at"]

    def __str__(self):
        return f"{self.customer_name} {self.percentage}% ({self.pharmacy_tin})"


class PendingSale(models.Model):
    STATUS_AWAITING_MANAGER = "awaiting_manager"
    STATUS_AWAITING_PHARMACIST = "awaiting_pharmacist"
    STATUS_REJECTED = "rejected"
    STATUS_SETTLED = "settled"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_AWAITING_MANAGER, "Awaiting manager"),
        (STATUS_AWAITING_PHARMACIST, "Awaiting pharmacist"),
        (STATUS_REJECTED, "Rejected by manager"),
        (STATUS_SETTLED, "Settled"),
        (STATUS_FAILED, "Failed by pharmacist"),
    ]

    pharmacy_tin = models.CharField(max_length=50, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_AWAITING_MANAGER,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_sales_created",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_sales_reviewed",
    )
    manager_reject_reason = models.TextField(blank=True, default="")
    customer_name = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PendingSale #{self.pk} ({self.status})"


class PendingSaleLine(models.Model):
    TRIGGER_NONE = "none"
    TRIGGER_QUANTITY_BAND = "quantity_band"
    TRIGGER_NEEDS_APPROVAL = "needs_approval"

    TRIGGER_CHOICES = [
        (TRIGGER_NONE, "None"),
        (TRIGGER_QUANTITY_BAND, "Quantity band"),
        (TRIGGER_NEEDS_APPROVAL, "Needs approval"),
    ]

    pending_sale = models.ForeignKey(
        PendingSale,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_sale_lines",
    )
    medicine_name = models.CharField(max_length=255)
    original_quantity = models.PositiveIntegerField()
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    trigger = models.CharField(max_length=32, choices=TRIGGER_CHOICES, default=TRIGGER_NONE)
    is_attachment = models.BooleanField(default=False)
    parent_line = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
    )
    manager_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    qty_threshold = models.PositiveIntegerField(null=True, blank=True)
    qty_final = models.PositiveIntegerField(null=True, blank=True)
    pharmacist_quantity = models.PositiveIntegerField(null=True, blank=True)
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    list_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def effective_price(self):
        return self.manager_unit_price if self.manager_unit_price is not None else self.original_price

    def __str__(self):
        return f"{self.medicine_name} x{self.original_quantity}"
