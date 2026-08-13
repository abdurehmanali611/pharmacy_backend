"""Resolve setup/quarterly fees from the Apex pricing catalog (shared DB)."""

from __future__ import annotations

from .models import SubscriptionPricingRule

# Kept for compatibility with older catalog rows that used module tiers.
PRICING_TIER_MODULES = {"Inventory", "Sales", "Reports"}


def parse_modules(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if not isinstance(raw, list):
        return []
    return [str(m).strip() for m in raw if str(m).strip()]


def modules_for_pricing_lookup(modules) -> list[str]:
    return [m for m in parse_modules(modules) if m in PRICING_TIER_MODULES]


def build_modules_key(modules) -> str:
    return "|".join(sorted(set(modules_for_pricing_lookup(modules))))


def fallback_pricing(modules=None) -> dict:
    return {
        "setup_fee_etb": 15000,
        "quarterly_fee_etb": 5000,
        "yearly_fee_etb": 18000,
        "description": "",
    }


def resolve_pricing(business_type: str = "Pharmacy", modules=None) -> dict:
    bt = (business_type or "Pharmacy").strip() or "Pharmacy"
    key = build_modules_key(modules or [])

    row = (
        SubscriptionPricingRule.objects.filter(
            business_type=bt,
            modules_key=key,
            is_active=True,
        )
        .order_by("sort_order", "id")
        .first()
    )

    # Prefer any active Pharmacy base rule if exact key is missing.
    if row is None and key == "":
        row = (
            SubscriptionPricingRule.objects.filter(
                business_type=bt,
                is_active=True,
            )
            .order_by("sort_order", "id")
            .first()
        )

    if row:
        return {
            "setup_fee_etb": int(row.setup_fee_etb or 0),
            "quarterly_fee_etb": int(row.quarterly_fee_etb or 0),
            "yearly_fee_etb": int(row.yearly_fee_etb or 0),
            "pricing_rule_id": row.id,
            "source": "catalog",
            "modules_key": row.modules_key or key,
            "description": (row.description or "").strip(),
        }

    fees = fallback_pricing(modules)
    return {
        **fees,
        "pricing_rule_id": None,
        "source": "fallback",
        "modules_key": key,
    }
