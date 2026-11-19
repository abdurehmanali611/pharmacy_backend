from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    full_name = models.CharField(max_length=255, blank=True)
    # Sales agents share one visible username; their own password tells them apart.
    login_name = models.CharField(max_length=150, blank=True, db_index=True)
    # Keyed fingerprint of a sales agent's password, used to keep passwords unique platform-wide.
    password_fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    pharmacy_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=100, blank=True)
    logoUrl = models.URLField(blank=True)
    pharmacy_tin = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username

