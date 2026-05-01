from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter

from .models import Invoice
from .serializers import InvoiceSerializer


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = [
        "invoice_number",
        "invoice_status",
        "invoice_type",
        "invoice_payment_method",
        "supplier__supplier_name",
    ]
    ordering_fields = [
        "invoice_number",
        "invoice_date",
        "invoice_amount",
        "invoice_status",
        "invoice_type",
        "created_at",
        "updated_at",
    ]
    ordering = ["-invoice_date", "-created_at"]

    def get_queryset(self):
        profile = getattr(self.request.user, "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        if not pharmacy_tin:
            return Invoice.objects.none()
        return super().get_queryset().filter(pharmacy_tin=pharmacy_tin).select_related("supplier")

    def perform_create(self, serializer):
        profile = getattr(self.request.user, "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        if not pharmacy_tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})
        serializer.save(pharmacy_tin=pharmacy_tin)

    def perform_update(self, serializer):
        profile = getattr(self.request.user, "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        if not pharmacy_tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})
        serializer.save(pharmacy_tin=pharmacy_tin)

