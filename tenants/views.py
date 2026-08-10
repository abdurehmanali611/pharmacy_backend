from django.contrib.auth import get_user_model
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import (
    PAYMENT_CHANNELS,
    billing_snapshot,
    create_payment_submission,
    resolve_login_access,
)
from .models import TenantAccount, TenantPaymentSubmission

User = get_user_model()


class SubmitTenantPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "profile", None)
        if not profile or (profile.role or "").strip().lower() != "manager":
            return Response(
                {"detail": "Only pharmacy managers can submit payments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tin = (profile.pharmacy_tin or "").strip()
        tenant = TenantAccount.objects.filter(pharmacy_tin=tin).first()
        if not tenant:
            return Response({"detail": "Tenant account not found."}, status=status.HTTP_404_NOT_FOUND)

        if tenant.is_illustration or tenant.billing_hold:
            return Response(
                {"detail": "Billing actions are disabled for this pharmacy."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        access = resolve_login_access(tenant, role=profile.role)
        payment_kind = (request.data.get("payment_kind") or access.payment_kind or "").strip().lower()
        if access.access_mode == "full" and payment_kind == TenantPaymentSubmission.KIND_SETUP:
            # allow setup submit only when unpaid
            if tenant.setup_fee_approved:
                return Response(
                    {"detail": "Setup fee is already approved."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif access.access_mode != "payment_portal" and access.period_status not in {
            "trial_expired",
            "grace",
            "expired",
            "trial",
            "trial_ending",
        }:
            if not (
                payment_kind == TenantPaymentSubmission.KIND_SETUP and not tenant.setup_fee_approved
            ):
                return Response(
                    {"detail": "No payment is required right now."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            submission = create_payment_submission(
                tenant=tenant,
                payment_kind=payment_kind,
                payment_channel=request.data.get("payment_channel", ""),
                transaction_ref=request.data.get("transaction_ref", ""),
                submitted_by=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        tenant.refresh_from_db()
        return Response(
            {
                "submission": {
                    "id": submission.id,
                    "payment_kind": submission.payment_kind,
                    "amount_etb": submission.amount_etb,
                    "payment_channel": submission.payment_channel,
                    "transaction_ref": submission.transaction_ref,
                    "status": submission.status,
                    "submitted_at": submission.submitted_at,
                },
                "billing": billing_snapshot(tenant),
                "access_mode": "denied"
                if payment_kind == TenantPaymentSubmission.KIND_SETUP
                else "payment_portal",
                "payment_kind": payment_kind,
                "detail": "Payment submitted. Apex will review shortly.",
            },
            status=status.HTTP_201_CREATED,
        )


class BillingMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "profile", None)
        if not profile:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        tenant = TenantAccount.objects.filter(pharmacy_tin=profile.pharmacy_tin).first()
        if not tenant:
            return Response({"detail": "Tenant account not found."}, status=status.HTTP_404_NOT_FOUND)

        access = resolve_login_access(tenant, role=profile.role)
        pending = (
            TenantPaymentSubmission.objects.filter(
                pharmacy_tin=tenant.pharmacy_tin,
                status=TenantPaymentSubmission.STATUS_PENDING,
            )
            .order_by("-submitted_at")
            .first()
        )
        return Response(
            {
                "billing": billing_snapshot(tenant),
                "access_mode": access.access_mode,
                "payment_kind": access.payment_kind,
                "period_status": access.period_status,
                "channels": list(PAYMENT_CHANNELS),
                "pending_submission": None
                if not pending
                else {
                    "id": pending.id,
                    "payment_kind": pending.payment_kind,
                    "amount_etb": pending.amount_etb,
                    "payment_channel": pending.payment_channel,
                    "transaction_ref": pending.transaction_ref,
                    "status": pending.status,
                    "submitted_at": pending.submitted_at,
                },
            }
        )
