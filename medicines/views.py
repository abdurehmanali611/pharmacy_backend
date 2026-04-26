from django.utils.dateparse import parse_date
from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from .models import Medicine
from .serializers import MedicineSerializer

class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "supplier_name", "supplier_phone", "supplier_email", "description"]
    ordering_fields = ["created_at", "updated_at", "name", "quantity", "price", "cost"]
    ordering = ["-created_at"]

    def get_queryset(self):
        profile = getattr(self.request.user, "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        if not pharmacy_tin:
            return Medicine.objects.none()
        qs = super().get_queryset().filter(pharmacy_tin=pharmacy_tin)

        # Optional filter by day the medicine was registered/created.
        created_date = self.request.query_params.get("created_date")
        if created_date:
            parsed = parse_date(created_date)
            if not parsed:
                raise ValidationError({"created_date": ["Invalid date format. Use YYYY-MM-DD."]})
            qs = qs.filter(created_at__date=parsed)

        return qs
    
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