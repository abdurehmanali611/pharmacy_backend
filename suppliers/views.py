from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter

from invoices.models import Invoice
from medicines.models import Medicine

from .models import Supplier
from .serializers import SupplierSerializer


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["supplier_name", "supplier_phone", "supplier_email"]
    ordering_fields = ["supplier_name", "created_at", "updated_at"]
    ordering = ["supplier_name", "-created_at"]

    def get_queryset(self):
        profile = getattr(self.request.user, "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        if not pharmacy_tin:
            return Supplier.objects.none()
        return super().get_queryset().filter(pharmacy_tin=pharmacy_tin)

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

    def perform_destroy(self, instance):
        if instance.medicines.exists() or instance.invoices.exists():
            raise ValidationError(
                {
                    "detail": "This supplier is still linked to medicines or invoices. Reassign those records before deleting the supplier."
                }
            )
        instance.delete()
