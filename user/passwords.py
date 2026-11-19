"""
Sales agents of every pharmacy sign in with a shared username plus their own password,
so a password may belong to only one agent across the whole platform (all pharmacies).

Django only stores salted hashes, which cannot be compared across users, so each agent
profile also keeps a keyed, slow fingerprint of the password. It is derived with PBKDF2
and the server secret, so it is as hard to reverse as a normal password hash.
"""
import hashlib

from django.conf import settings

from .models import UserProfile

TAKEN_MESSAGE = "This password is already used by another sales agent. Please choose a different one."


def password_fingerprint(raw: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        raw.encode("utf-8"),
        ("sales-agent-password:" + settings.SECRET_KEY).encode("utf-8"),
        60_000,
    ).hex()


def agent_password_taken(raw: str, exclude_user=None) -> bool:
    """True if any sales agent, in any pharmacy, already uses this password."""
    agents = UserProfile.objects.filter(role__iexact="pharmacist")
    if exclude_user is not None:
        agents = agents.exclude(user=exclude_user)
    if agents.filter(password_fingerprint=password_fingerprint(raw)).exists():
        return True
    # Agents created before fingerprints existed: fall back to checking their real hash.
    for profile in agents.filter(password_fingerprint="").select_related("user"):
        if profile.user.check_password(raw):
            return True
    return False


def store_fingerprint(user, raw: str) -> None:
    UserProfile.objects.filter(user=user).update(password_fingerprint=password_fingerprint(raw))
