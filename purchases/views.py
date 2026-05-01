from django.db import transaction
from decimal import Decimal
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
from .models import Purchase
from .serializers import PurchaseSerializer
from medicines.models import Medicine


class BulkPurchaseItemSerializer(serializers.Serializer):
    medicine_name = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))


class BulkPurchaseSerializer(serializers.Serializer):
    items = BulkPurchaseItemSerializer(many=True)

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

    def _get_pharmacy_tin(self):
        profile = getattr(self.request.user, "profile", None)
        return getattr(profile, "pharmacy_tin", "")

    def _get_medicine_for_pharmacy(self, medicine_name, pharmacy_tin):
        return Medicine.objects.filter(pharmacy_tin=pharmacy_tin, name=medicine_name).first()
    
    def perform_create(self, serializer):
        pharmacy_tin = self._get_pharmacy_tin()
        if not pharmacy_tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})

        # On create, serializer.instance is None.
        medicine_name = serializer.validated_data.get("medicine_name")
        requested_quantity = serializer.validated_data.get("quantity") or 0

        medicine = self._get_medicine_for_pharmacy(medicine_name, pharmacy_tin)
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
        pharmacy_tin = self._get_pharmacy_tin()
        if not pharmacy_tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})

        old_purchase: Purchase = serializer.instance
        new_medicine_name = serializer.validated_data.get("medicine_name", old_purchase.medicine_name)
        new_quantity = serializer.validated_data.get("quantity", old_purchase.quantity)

        if new_quantity <= 0:
            raise ValidationError({"quantity": ["Quantity must be greater than zero."]})

        with transaction.atomic():
            # Restock the old medicine, then decrement the new one.
            old_medicine = self._get_medicine_for_pharmacy(old_purchase.medicine_name, pharmacy_tin)
            if old_medicine:
                old_medicine.quantity = old_medicine.quantity + old_purchase.quantity
                old_medicine.save(update_fields=["quantity"])

            new_medicine = self._get_medicine_for_pharmacy(new_medicine_name, pharmacy_tin)
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
        pharmacy_tin = self._get_pharmacy_tin()
        if not pharmacy_tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})

        with transaction.atomic():
            medicine = self._get_medicine_for_pharmacy(instance.medicine_name, pharmacy_tin)
            if medicine:
                medicine.quantity = medicine.quantity + instance.quantity
                medicine.save(update_fields=["quantity"])
            instance.delete()

    @action(detail=False, methods=["post"], url_path="bulk_create")
    def bulk_create(self, request):
        pharmacy_tin = self._get_pharmacy_tin()
        if not pharmacy_tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})

        serializer = BulkPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data["items"]

        if not items:
            raise ValidationError({"items": ["Please add at least one medicine to sell."]})

        aggregated_quantities = {}
        medicine_map = {}

        for item in items:
            medicine_name = item["medicine_name"]
            medicine = self._get_medicine_for_pharmacy(medicine_name, pharmacy_tin)
            if not medicine:
                raise ValidationError({"items": [f"{medicine_name}: Medicine not found in inventory."]})

            aggregated_quantities[medicine_name] = aggregated_quantities.get(medicine_name, 0) + item["quantity"]
            medicine_map[medicine_name] = medicine

        for medicine_name, total_quantity in aggregated_quantities.items():
            medicine = medicine_map[medicine_name]
            if medicine.quantity < total_quantity:
                raise ValidationError(
                    {
                        "items": [
                            f"{medicine_name}: Insufficient stock. Available: {medicine.quantity}, requested: {total_quantity}."
                        ]
                    }
                )

        created_purchases = []

        with transaction.atomic():
            for item in items:
                medicine_name = item["medicine_name"]
                medicine = medicine_map[medicine_name]
                quantity = item["quantity"]
                price = item["price"]

                medicine.quantity = medicine.quantity - quantity
                medicine.save(update_fields=["quantity"])

                purchase = Purchase.objects.create(
                    pharmacy_tin=pharmacy_tin,
                    medicine_name=medicine_name,
                    quantity=quantity,
                    price=price,
                    total_price=quantity * price,
                    cost_price=medicine.cost,
                )
                created_purchases.append(purchase)

        return Response(
            {
                "detail": f"Recorded {len(created_purchases)} sale item(s).",
                "results": PurchaseSerializer(created_purchases, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )
