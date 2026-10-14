from decimal import Decimal

from django.db import transaction
from django.db.models import Case, F, IntegerField, Value, When
from django.utils import timezone
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
from .models import Purchase
from .serializers import PurchaseSerializer
from medicines.models import Medicine


class BulkPurchaseItemSerializer(serializers.Serializer):
    medicine_id = serializers.IntegerField(required=False)
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

    def _get_pharmacy_tin(self):
        profile = getattr(self.request.user, "profile", None)
        return getattr(profile, "pharmacy_tin", "")

    def _get_medicine_for_pharmacy(self, medicine_name, pharmacy_tin, medicine_id=None):
        medicines = Medicine.objects.filter(pharmacy_tin=pharmacy_tin)
        if medicine_id is not None:
            return medicines.filter(pk=medicine_id, name=medicine_name).first()

        today = timezone.localdate()
        return medicines.filter(name=medicine_name).order_by(
            Case(
                When(expiry_date__lt=today, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            F("expiry_date").asc(nulls_last=True),
            "created_at",
        ).first()

    def _validate_not_expired(self, medicine):
        if medicine.expiry_date and medicine.expiry_date < timezone.localdate():
            raise ValidationError(
                {"medicine_name": [f"{medicine.name}: Expired stock cannot be sold."]}
            )
    
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
        self._validate_not_expired(medicine)
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

        with transaction.atomic():
            # Decrement stock when recording a sale.
            medicine.quantity = medicine.quantity - requested_quantity
            medicine.save(update_fields=["quantity"])

            serializer.save(
                pharmacy_tin=pharmacy_tin,
                medicine=medicine,
                cost_price=medicine.cost,
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
            old_medicine = old_purchase.medicine
            if old_medicine is None or old_medicine.pharmacy_tin != pharmacy_tin:
                old_medicine = self._get_medicine_for_pharmacy(old_purchase.medicine_name, pharmacy_tin)
            if old_medicine:
                old_medicine.quantity = old_medicine.quantity + old_purchase.quantity
                old_medicine.save(update_fields=["quantity"])

            new_medicine = (
                old_medicine
                if old_medicine and new_medicine_name == old_purchase.medicine_name
                else self._get_medicine_for_pharmacy(new_medicine_name, pharmacy_tin)
            )
            if not new_medicine:
                raise ValidationError({"medicine_name": ["Medicine not found in inventory."]})
            self._validate_not_expired(new_medicine)
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

            serializer.save(
                pharmacy_tin=pharmacy_tin,
                medicine=new_medicine,
                cost_price=new_medicine.cost,
            )

    def perform_destroy(self, instance: Purchase):
        pharmacy_tin = self._get_pharmacy_tin()
        if not pharmacy_tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})

        with transaction.atomic():
            medicine = instance.medicine
            if medicine is None or medicine.pharmacy_tin != pharmacy_tin:
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
        medicine_ids_for_items = []

        for item in items:
            medicine_name = item["medicine_name"]
            medicine = self._get_medicine_for_pharmacy(
                medicine_name,
                pharmacy_tin,
                item.get("medicine_id"),
            )
            if not medicine:
                raise ValidationError({"items": [f"{medicine_name}: Medicine not found in inventory."]})
            self._validate_not_expired(medicine)

            aggregated_quantities[medicine.pk] = aggregated_quantities.get(medicine.pk, 0) + item["quantity"]
            medicine_map[medicine.pk] = medicine
            medicine_ids_for_items.append(medicine.pk)

        created_purchases = []

        with transaction.atomic():
            locked_medicines = {
                medicine.pk: medicine
                for medicine in Medicine.objects.select_for_update().filter(
                    pharmacy_tin=pharmacy_tin,
                    pk__in=medicine_map,
                )
            }
            if len(locked_medicines) != len(medicine_map):
                raise ValidationError({"items": ["A selected medicine batch is no longer available."]})

            for medicine_id, total_quantity in aggregated_quantities.items():
                medicine = locked_medicines[medicine_id]
                self._validate_not_expired(medicine)
                if medicine.quantity < total_quantity:
                    raise ValidationError(
                        {
                            "items": [
                                f"{medicine.name}: Insufficient stock. Available: {medicine.quantity}, requested: {total_quantity}."
                            ]
                        }
                    )

            for item, medicine_id in zip(items, medicine_ids_for_items):
                medicine = locked_medicines[medicine_id]
                medicine_name = item["medicine_name"]
                quantity = item["quantity"]
                price = item["price"]

                medicine.quantity = medicine.quantity - quantity
                medicine.save(update_fields=["quantity"])

                purchase = Purchase.objects.create(
                    pharmacy_tin=pharmacy_tin,
                    medicine=medicine,
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
