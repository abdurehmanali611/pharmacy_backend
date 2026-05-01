from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter

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
        supplier = serializer.save(pharmacy_tin=pharmacy_tin)
        Medicine.objects.filter(pharmacy_tin=pharmacy_tin, supplier=supplier).update(
            supplier_name=supplier.supplier_name,
            supplier_phone=supplier.supplier_phone,
            supplier_email=supplier.supplier_email,
        )
