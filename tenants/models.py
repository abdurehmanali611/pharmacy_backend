from django.db import models


class TenantAccount(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"
    STATUS_BANNED = "banned"
    STATUS_DELETED = "deleted"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_BANNED, "Banned"),
        (STATUS_DELETED, "Deleted"),
    ]

    pharmacy_tin = models.CharField(max_length=50, unique=True, db_index=True)
    pharmacy_name = models.CharField(max_length=255, blank=True, default="")
    logo_url = models.URLField(blank=True, default="")
    account_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    status_reason = models.TextField(blank=True, default="")
    status_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.pharmacy_name or self.pharmacy_tin} ({self.account_status})"
