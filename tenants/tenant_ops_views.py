"""Tenant-facing module requests and Apex chat (shared tables with pharmacy-admin)."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    TenantAccount,
    TenantFeedbackMessage,
    TenantFeedbackThread,
    TenantModuleChangeRequest,
)

PHARMACY_MODULES = ["Inventory", "Sales", "Reports"]


def _manager_tin(request):
    profile = getattr(request.user, "profile", None)
    if not profile or (profile.role or "").strip().lower() != "manager":
        return None, Response(
            {"detail": "Only pharmacy managers can perform this action."},
            status=status.HTTP_403_FORBIDDEN,
        )
    tin = (profile.pharmacy_tin or "").strip()
    if not tin:
        return None, Response({"detail": "Pharmacy TIN missing."}, status=400)
    return tin, None


class TenantModulesMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tin, err = _manager_tin(request)
        if err:
            return err
        tenant = TenantAccount.objects.filter(pharmacy_tin=tin).first()
        if not tenant:
            return Response({"detail": "Tenant not found."}, status=404)
        pending = TenantModuleChangeRequest.objects.filter(
            pharmacy_tin=tin, status=TenantModuleChangeRequest.STATUS_PENDING
        ).first()
        return Response(
            {
                "modules": tenant.modules or [],
                "available_modules": PHARMACY_MODULES,
                "pending_request": (
                    {
                        "id": pending.id,
                        "requested_modules": pending.requested_modules,
                        "request_note": pending.request_note,
                        "created_at": pending.created_at,
                    }
                    if pending
                    else None
                ),
            }
        )


class RequestModuleChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        tin, err = _manager_tin(request)
        if err:
            return err
        tenant = TenantAccount.objects.filter(pharmacy_tin=tin).first()
        if not tenant:
            return Response({"detail": "Tenant not found."}, status=404)
        if TenantModuleChangeRequest.objects.filter(
            pharmacy_tin=tin, status=TenantModuleChangeRequest.STATUS_PENDING
        ).exists():
            return Response(
                {"detail": "A pending module request already exists."},
                status=400,
            )
        modules = request.data.get("modules") or []
        if not isinstance(modules, list):
            return Response({"detail": "modules must be a list."}, status=400)
        cleaned = [str(m).strip() for m in modules if str(m).strip() in PHARMACY_MODULES]
        note = (request.data.get("note") or "").strip()
        current = tenant.modules or []
        req = TenantModuleChangeRequest.objects.create(
            pharmacy_tin=tin,
            requested_modules=cleaned,
            request_note=note
            or f"[Module change] current={current} projected={cleaned}",
            status=TenantModuleChangeRequest.STATUS_PENDING,
            requested_by_side="tenant",
            requested_by_username=request.user.username,
        )
        return Response(
            {"id": req.id, "status": req.status, "requested_modules": req.requested_modules},
            status=201,
        )


class TenantFeedbackInboxView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "profile", None)
        if not profile:
            return Response({"detail": "Profile required."}, status=403)
        tin = (profile.pharmacy_tin or "").strip()
        if not tin:
            return Response({"detail": "Pharmacy TIN missing."}, status=400)
        thread, _ = TenantFeedbackThread.objects.get_or_create(pharmacy_tin=tin)
        unread = TenantFeedbackMessage.objects.filter(
            thread=thread,
            sender_side=TenantFeedbackMessage.SIDE_APEX,
            read_by_tenant=False,
        ).count()
        TenantFeedbackMessage.objects.filter(
            thread=thread,
            sender_side=TenantFeedbackMessage.SIDE_APEX,
            read_by_tenant=False,
        ).update(read_by_tenant=True)
        messages = [
            {
                "id": m.id,
                "sender_side": m.sender_side,
                "body": m.body,
                "image_url": m.image_url,
                "sender_username": m.sender_username,
                "created_at": m.created_at,
            }
            for m in thread.messages.all()
        ]
        return Response(
            {
                "thread_id": thread.id,
                "status": thread.status,
                "unread_from_apex": unread,
                "messages": messages,
            }
        )


class SendTenantFeedbackView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "profile", None)
        if not profile:
            return Response({"detail": "Profile required."}, status=403)
        tin = (profile.pharmacy_tin or "").strip()
        body = (request.data.get("body") or "").strip()
        if not tin or not body:
            return Response({"detail": "body is required."}, status=400)
        thread, _ = TenantFeedbackThread.objects.get_or_create(pharmacy_tin=tin)
        if thread.status == TenantFeedbackThread.STATUS_CLOSED:
            thread.status = TenantFeedbackThread.STATUS_OPEN
            thread.closed_at = None
            thread.save(update_fields=["status", "closed_at", "updated_at"])
        msg = TenantFeedbackMessage.objects.create(
            thread=thread,
            sender_side=TenantFeedbackMessage.SIDE_TENANT,
            body=body,
            image_url=(request.data.get("image_url") or "").strip(),
            sender_username=request.user.username,
            read_by_tenant=True,
            read_by_apex=False,
        )
        thread.updated_at = timezone.now()
        thread.save(update_fields=["updated_at"])
        return Response(
            {
                "id": msg.id,
                "sender_side": msg.sender_side,
                "body": msg.body,
                "created_at": msg.created_at,
            },
            status=201,
        )
