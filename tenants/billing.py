from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from .models import TenantAccount, TenantPaymentSubmission

PERIOD_DAYS = 90
WARNING_DAYS = 10
TRIAL_ENDING_DAYS = 5  # HotCol-aligned soft window before trial final day
GRACE_DAYS = 10

DEFAULT_SETUP_FEE_ETB = 15000
DEFAULT_QUARTERLY_FEE_ETB = 5000


def catalog_default_fees() -> dict:
    """Active Pharmacy base catalog fees from Apex pricing rules (shared DB)."""
    try:
        from .pricing import resolve_pricing

        fees = resolve_pricing("Pharmacy", [])
        return {
            "setup_fee_etb": int(fees.get("setup_fee_etb") or DEFAULT_SETUP_FEE_ETB),
            "quarterly_fee_etb": int(fees.get("quarterly_fee_etb") or DEFAULT_QUARTERLY_FEE_ETB),
            "yearly_fee_etb": int(fees.get("yearly_fee_etb") or 0),
            "source": fees.get("source") or "fallback",
            "description": fees.get("description") or "",
        }
    except Exception:
        return {
            "setup_fee_etb": DEFAULT_SETUP_FEE_ETB,
            "quarterly_fee_etb": DEFAULT_QUARTERLY_FEE_ETB,
            "yearly_fee_etb": 0,
            "source": "fallback",
            "description": "",
        }

PAYMENT_CHANNELS = (
    "Telebirr",
    "Commercial Bank of Ethiopia",
)


@dataclass
class AccessDecision:
    access_mode: str  # full | payment_portal | denied
    payment_kind: str | None
    period_status: str
    detail: str = ""


def compute_subscription_paid_until(*, started_at, periods: int):
    if not started_at or periods <= 0:
        return None
    return started_at + timedelta(days=PERIOD_DAYS * periods)


def compute_period_status(tenant: TenantAccount, *, now=None) -> str:
    now = now or timezone.now()

    if tenant.is_illustration:
        return "exempt"
    if tenant.billing_hold:
        return "on_hold"

    setup_fee = int(tenant.setup_fee_etb or 0)
    if setup_fee > 0 and not tenant.setup_fee_approved:
        has_pending = TenantPaymentSubmission.objects.filter(
            pharmacy_tin=tenant.pharmacy_tin,
            payment_kind=TenantPaymentSubmission.KIND_SETUP,
            status=TenantPaymentSubmission.STATUS_PENDING,
        ).exists()
        has_ref = len((tenant.payment_transaction_ref or "").strip()) >= 4
        if has_pending or has_ref:
            return "setup_pending"
        if tenant.free_trial_ends_at:
            # Soft window until the day before the trial ends; final day+ blocks login.
            if now.date() < tenant.free_trial_ends_at.date():
                remaining = tenant.free_trial_ends_at - now
                if remaining <= timedelta(days=TRIAL_ENDING_DAYS):
                    return "trial_ending"
                return "trial"
            return "trial_expired"
        # No trial and unpaid setup without submission yet → treat as portal setup
        return "trial_expired"

    quarterly_fee = int(tenant.quarterly_fee_etb or 0)
    if quarterly_fee <= 0:
        return "active" if tenant.setup_fee_approved or setup_fee <= 0 else "setup_pending"

    paid_until = tenant.subscription_paid_until
    if not paid_until:
        return "expired"

    # Soft access while days remain after today; final calendar day and after → hard gate.
    if now.date() < paid_until.date():
        if paid_until - now <= timedelta(days=WARNING_DAYS):
            return "warning"
        return "active"

    overdue = now - paid_until
    # Final day counts as day 0 of the grace/overdue window.
    if overdue.total_seconds() < 0:
        overdue = timedelta(0)
    if overdue <= timedelta(days=GRACE_DAYS):
        return "grace"
    return "expired"


def resolve_login_access(tenant: TenantAccount, *, role: str) -> AccessDecision:
    role_l = (role or "").strip().lower()
    is_manager = role_l == "manager"
    period = compute_period_status(tenant)

    if period == "on_hold":
        return AccessDecision(
            "denied",
            None,
            period,
            "This pharmacy is on billing hold. Login is disabled until Apex releases the hold.",
        )

    if period in {"exempt", "trial", "trial_ending", "active", "warning"}:
        return AccessDecision("full", None, period)

    if period == "setup_pending":
        return AccessDecision(
            "denied",
            TenantPaymentSubmission.KIND_SETUP,
            period,
            "Setup payment is awaiting Apex approval.",
        )

    if period == "trial_expired":
        if is_manager:
            return AccessDecision("payment_portal", TenantPaymentSubmission.KIND_SETUP, period)
        return AccessDecision(
            "denied",
            TenantPaymentSubmission.KIND_SETUP,
            period,
            "Setup payment is required. Ask your manager to complete payment verification.",
        )

    if period in {"grace", "expired"}:
        if is_manager:
            return AccessDecision(
                "payment_portal",
                TenantPaymentSubmission.KIND_QUARTERLY,
                period,
            )
        return AccessDecision(
            "denied",
            TenantPaymentSubmission.KIND_QUARTERLY,
            period,
            "Subscription payment is required. Ask your manager to renew.",
        )

    return AccessDecision("denied", None, period, "Access denied.")


def create_payment_submission(
    *,
    tenant: TenantAccount,
    payment_kind: str,
    payment_channel: str,
    transaction_ref: str,
    submitted_by=None,
) -> TenantPaymentSubmission:
    kind = payment_kind.strip().lower()
    channel = payment_channel.strip()
    ref = transaction_ref.strip()

    if kind not in {
        TenantPaymentSubmission.KIND_SETUP,
        TenantPaymentSubmission.KIND_QUARTERLY,
    }:
        raise ValueError("payment_kind must be setup or quarterly.")
    if channel not in PAYMENT_CHANNELS:
        raise ValueError("Invalid payment channel.")
    if len(ref) < 4:
        raise ValueError("Transaction reference must be at least 4 characters.")

    amount = (
        int(tenant.setup_fee_etb or 0)
        if kind == TenantPaymentSubmission.KIND_SETUP
        else int(tenant.quarterly_fee_etb or 0)
    )
    if amount <= 0:
        raise ValueError("No fee configured for this payment kind.")

    TenantPaymentSubmission.objects.filter(
        pharmacy_tin=tenant.pharmacy_tin,
        payment_kind=kind,
        status=TenantPaymentSubmission.STATUS_PENDING,
    ).update(
        status=TenantPaymentSubmission.STATUS_REJECTED,
        rejected_at=timezone.now(),
        rejection_reason="Superseded by a newer submission.",
    )

    quarter_number = None
    if kind == TenantPaymentSubmission.KIND_QUARTERLY:
        quarter_number = int(tenant.paid_quarters_count or 0) + 1

    submission = TenantPaymentSubmission.objects.create(
        pharmacy_tin=tenant.pharmacy_tin,
        payment_kind=kind,
        amount_etb=amount,
        payment_channel=channel,
        transaction_ref=ref,
        submitted_by=submitted_by if getattr(submitted_by, "is_authenticated", False) else None,
        quarter_number=quarter_number,
    )

    tenant.payment_channel = channel
    tenant.payment_transaction_ref = ref
    update_fields = ["payment_channel", "payment_transaction_ref", "updated_at"]
    if kind == TenantPaymentSubmission.KIND_QUARTERLY:
        tenant.subscription_payment_approved = False
        update_fields.append("subscription_payment_approved")
    tenant.save(update_fields=update_fields)
    return submission


def approve_setup_payment(*, tenant: TenantAccount, approved_by=None) -> TenantAccount:
    now = timezone.now()
    pending = (
        TenantPaymentSubmission.objects.filter(
            pharmacy_tin=tenant.pharmacy_tin,
            payment_kind=TenantPaymentSubmission.KIND_SETUP,
            status=TenantPaymentSubmission.STATUS_PENDING,
        )
        .order_by("-submitted_at")
        .first()
    )
    if pending:
        pending.status = TenantPaymentSubmission.STATUS_APPROVED
        pending.approved_at = now
        pending.approved_by = approved_by
        pending.save(update_fields=["status", "approved_at", "approved_by"])

    billing_applies = int(tenant.quarterly_fee_etb or 0) > 0
    tenant.setup_fee_approved = True
    tenant.subscription_payment_approved = billing_applies
    tenant.paid_quarters_count = 1 if billing_applies else 0
    tenant.billing_started_at = now if billing_applies else None
    tenant.subscription_paid_until = (
        compute_subscription_paid_until(started_at=now, periods=1) if billing_applies else None
    )
    tenant.save(
        update_fields=[
            "setup_fee_approved",
            "subscription_payment_approved",
            "paid_quarters_count",
            "billing_started_at",
            "subscription_paid_until",
            "updated_at",
        ]
    )
    return tenant


def approve_quarterly_payment(*, tenant: TenantAccount, approved_by=None) -> TenantAccount:
    if int(tenant.quarterly_fee_etb or 0) <= 0:
        raise ValueError("Quarterly billing is not enabled for this tenant.")

    now = timezone.now()
    pending = (
        TenantPaymentSubmission.objects.filter(
            pharmacy_tin=tenant.pharmacy_tin,
            payment_kind=TenantPaymentSubmission.KIND_QUARTERLY,
            status=TenantPaymentSubmission.STATUS_PENDING,
        )
        .order_by("-submitted_at")
        .first()
    )
    if pending:
        pending.status = TenantPaymentSubmission.STATUS_APPROVED
        pending.approved_at = now
        pending.approved_by = approved_by
        pending.save(update_fields=["status", "approved_at", "approved_by"])

    next_periods = int(tenant.paid_quarters_count or 0) + 1
    started = tenant.billing_started_at or tenant.created_at or now
    if not tenant.billing_started_at:
        tenant.billing_started_at = started

    tenant.subscription_payment_approved = True
    tenant.paid_quarters_count = next_periods
    tenant.subscription_paid_until = compute_subscription_paid_until(
        started_at=started,
        periods=next_periods,
    )
    tenant.save(
        update_fields=[
            "subscription_payment_approved",
            "paid_quarters_count",
            "subscription_paid_until",
            "billing_started_at",
            "updated_at",
        ]
    )
    return tenant


def reject_payment_submission(*, submission: TenantPaymentSubmission, reason: str, rejected_by=None):
    submission.status = TenantPaymentSubmission.STATUS_REJECTED
    submission.rejection_reason = (reason or "").strip()
    submission.rejected_at = timezone.now()
    submission.rejected_by = rejected_by
    submission.save(
        update_fields=["status", "rejection_reason", "rejected_at", "rejected_by"]
    )
    return submission


def release_billing_hold(*, tenant: TenantAccount) -> TenantAccount:
    now = timezone.now()
    billing_applies = int(tenant.quarterly_fee_etb or 0) > 0
    tenant.billing_hold = False
    tenant.billing_started_at = now
    if billing_applies and tenant.setup_fee_approved:
        tenant.paid_quarters_count = max(int(tenant.paid_quarters_count or 0), 1)
        tenant.subscription_payment_approved = True
        tenant.subscription_paid_until = compute_subscription_paid_until(
            started_at=now,
            periods=tenant.paid_quarters_count,
        )
    tenant.save(
        update_fields=[
            "billing_hold",
            "billing_started_at",
            "paid_quarters_count",
            "subscription_payment_approved",
            "subscription_paid_until",
            "updated_at",
        ]
    )
    return tenant


def billing_snapshot(tenant: TenantAccount) -> dict:
    period = compute_period_status(tenant)
    return {
        "pharmacy_tin": tenant.pharmacy_tin,
        "setup_fee_etb": tenant.setup_fee_etb,
        "quarterly_fee_etb": tenant.quarterly_fee_etb,
        "setup_fee_approved": tenant.setup_fee_approved,
        "subscription_payment_approved": tenant.subscription_payment_approved,
        "subscription_paid_until": tenant.subscription_paid_until,
        "paid_quarters_count": tenant.paid_quarters_count,
        "billing_hold": tenant.billing_hold,
        "billing_started_at": tenant.billing_started_at,
        "free_trial_ends_at": tenant.free_trial_ends_at,
        "is_illustration": tenant.is_illustration,
        "billing_notes": tenant.billing_notes,
        "payment_channel": tenant.payment_channel,
        "payment_transaction_ref": tenant.payment_transaction_ref,
        "period_status": period,
    }
