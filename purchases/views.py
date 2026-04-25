from django.db import transaction
from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError
from .models import Purchase
from .serializers import PurchaseSerializer
from medicines.models import Medicine

class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = getattr(self.request.user, "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        if not pharmacy_tin:
            return Purchase.objects.none()
        return super().get_queryset().filter(pharmacy_tin=pharmacy_tin)

    def _get_medicine_cost(self, medicine_name):
        profile = getattr(self.request.user, "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        if not pharmacy_tin:
            return 0
        medicine = Medicine.objects.filter(pharmacy_tin=pharmacy_tin, name=medicine_name).first()
        return medicine.cost if medicine else 0
    
    def perform_create(self, serializer):
        profile = getattr(self.request.user, "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        if not pharmacy_tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})

        # On create, serializer.instance is None.
        medicine_name = serializer.validated_data.get("medicine_name")
        requested_quantity = serializer.validated_data.get("quantity") or 0

        medicine = Medicine.objects.filter(
            pharmacy_tin=pharmacy_tin,
            name=medicine_name,
        ).first()
        if not medicine:
            raise ValidationError({"medicine_name": ["Medicine not found in inventory."]})
        if requested_quantity <= 0:
            raise ValidationError({"quantity": ["Quantity must be greater than zero."]})
        if medicine.quantity < requested_quantity:
            raise ValidationError(
                {
                    "quantity": [
                        f"Insufficient stock. Available: {medicine.quantity}."
                    ]
                }
            )

        cost_price = self._get_medicine_cost(medicine_name)
        with transaction.atomic():
            # Decrement stock when recording a sale.
            medicine.quantity = medicine.quantity - requested_quantity
            medicine.save(update_fields=["quantity"])

            serializer.save(
                pharmacy_tin=pharmacy_tin,
                cost_price=cost_price,
            )

    def perform_update(self, serializer):
        profile = getattr(self.request.user, "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        if not pharmacy_tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})

        old_purchase: Purchase = serializer.instance
        new_medicine_name = serializer.validated_data.get("medicine_name", old_purchase.medicine_name)
        new_quantity = serializer.validated_data.get("quantity", old_purchase.quantity)

        if new_quantity <= 0:
            raise ValidationError({"quantity": ["Quantity must be greater than zero."]})

        with transaction.atomic():
            # Restock the old medicine, then decrement the new one.
            old_medicine = Medicine.objects.filter(pharmacy_tin=pharmacy_tin, name=old_purchase.medicine_name).first()
            if old_medicine:
                old_medicine.quantity = old_medicine.quantity + old_purchase.quantity
                old_medicine.save(update_fields=["quantity"])

            new_medicine = Medicine.objects.filter(pharmacy_tin=pharmacy_tin, name=new_medicine_name).first()
            if not new_medicine:
                raise ValidationError({"medicine_name": ["Medicine not found in inventory."]})
            if new_medicine.quantity < new_quantity:
                raise ValidationError(
                    {
                        "quantity": [
                            f"Insufficient stock. Available: {new_medicine.quantity}."
                        ]
                    }
                )

            new_medicine.quantity = new_medicine.quantity - new_quantity
            new_medicine.save(update_fields=["quantity"])

            cost_price = self._get_medicine_cost(new_medicine_name)
            serializer.save(
                pharmacy_tin=pharmacy_tin,
                cost_price=cost_price,
            )

    def perform_destroy(self, instance: Purchase):
        profile = getattr(self.request.user, "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        if not pharmacy_tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})

        with transaction.atomic():
            medicine = Medicine.objects.filter(pharmacy_tin=pharmacy_tin, name=instance.medicine_name).first()
            if medicine:
                medicine.quantity = medicine.quantity + instance.quantity
                medicine.save(update_fields=["quantity"])
            instance.delete()