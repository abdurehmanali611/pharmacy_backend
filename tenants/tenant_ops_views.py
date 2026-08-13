"""Tenant-facing Apex chat (shared tables with pharmacy-admin)."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    TenantFeedbackMessage,
    TenantFeedbackThread,
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
        mark_read = str(request.query_params.get("mark_read") or "").lower() in {
            "1",
            "true",
            "yes",
        }
        if mark_read and unread:
            TenantFeedbackMessage.objects.filter(
                thread=thread,
                sender_side=TenantFeedbackMessage.SIDE_APEX,
                read_by_tenant=False,
            ).update(read_by_tenant=True)
            unread = 0
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
        image_url = (request.data.get("image_url") or "").strip()
        if not tin or (not body and not image_url):
            return Response({"detail": "body or image_url is required."}, status=400)
        thread, _ = TenantFeedbackThread.objects.get_or_create(pharmacy_tin=tin)
        if thread.status == TenantFeedbackThread.STATUS_CLOSED:
            thread.status = TenantFeedbackThread.STATUS_OPEN
            thread.closed_at = None
            thread.save(update_fields=["status", "closed_at", "updated_at"])
        msg = TenantFeedbackMessage.objects.create(
            thread=thread,
            sender_side=TenantFeedbackMessage.SIDE_TENANT,
            body=body,
            image_url=image_url,
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
                "image_url": msg.image_url,
                "created_at": msg.created_at,
            },
            status=201,
        )
