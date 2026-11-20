from decimal import Decimal

from rest_framework import serializers

from suppliers.models import Supplier

from .models import CreditPayment, Medicine, StockLoss

class MedicineSerializer(serializers.ModelSerializer):
    supplier_id = serializers.PrimaryKeyRelatedField(
        source="supplier",
        queryset=Supplier.objects.none(),
        allow_null=True,
        required=False,
        write_only=True,
    )
    selected_supplier_id = serializers.IntegerField(source="supplier.id", read_only=True)
    supplier_name = serializers.SerializerMethodField()
    supplier_phone = serializers.SerializerMethodField()
    supplier_email = serializers.SerializerMethodField()
    paid_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal("0")
    )
    total_cost = serializers.SerializerMethodField()
    credit_amount = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = Medicine
        fields = [
            "id",
            "pharmacy_tin",
            "supplier_id",
            "selected_supplier_id",
            "name",
            "category",
            "price",
            "cost",
            "quantity",
            "received_quantity",
            "paid_amount",
            "total_cost",
            "credit_amount",
            "payment_status",
            "batch_number",
            "expiry_date",
            "description",
            "image_url",
            "supplier_name",
            "supplier_phone",
            "supplier_email",
            "created_at",
            "updated_at"
        ]
        read_only_fields = [
            "id",
            "pharmacy_tin",
            "selected_supplier_id",
            "supplier_name",
            "supplier_phone",
            "supplier_email",
            "received_quantity",
            "total_cost",
            "credit_amount",
            "payment_status",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        profile = getattr(getattr(request, "user", None), "profile", None)
        pharmacy_tin = getattr(profile, "pharmacy_tin", "")
        self.fields["supplier_id"].queryset = Supplier.objects.filter(pharmacy_tin=pharmacy_tin)

    def validate(self, attrs):
        supplier = attrs.get("supplier")
        if supplier is None and self.instance is not None:
            supplier = self.instance.supplier

        if supplier is None:
            raise serializers.ValidationError({"supplier_id": ["Please select a supplier."]})

        # What was bought (received qty x cost) is the ceiling for what can be paid.
        cost = attrs.get("cost", getattr(self.instance, "cost", Decimal("0")))
        if self.instance is None:
            received = attrs.get("quantity", 0)
        else:
            old_quantity = self.instance.quantity
            new_quantity = attrs.get("quantity", old_quantity)
            received = max(0, self.instance.received_quantity + (new_quantity - old_quantity))
        total = Decimal(received) * Decimal(cost)
        paid = attrs.get("paid_amount")
        if paid is not None and paid > total:
            raise serializers.ValidationError(
                {"paid_amount": [f"Paid amount cannot exceed the total cost ({total})."]}
            )
        return attrs

    def create(self, validated_data):
        quantity = validated_data.get("quantity", 0)
        cost = validated_data.get("cost", Decimal("0"))
        validated_data["received_quantity"] = quantity
        if validated_data.get("paid_amount") is None:
            validated_data["paid_amount"] = Decimal(quantity) * Decimal(cost)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "quantity" in validated_data:
            delta = validated_data["quantity"] - instance.quantity
            validated_data["received_quantity"] = max(0, instance.received_quantity + delta)
        return super().update(instance, validated_data)

    def _total(self, obj):
        return (Decimal(obj.received_quantity) * Decimal(obj.cost)).quantize(Decimal("0.01"))

    def get_total_cost(self, obj):
        return self._total(obj)

    def get_credit_amount(self, obj):
        owed = self._total(obj) - Decimal(obj.paid_amount)
        return owed if owed > Decimal("0.01") else Decimal("0.00")

    def get_payment_status(self, obj):
        return "credit" if self.get_credit_amount(obj) > 0 else "paid"

    def get_supplier_name(self, obj):
        return obj.supplier.supplier_name if obj.supplier else ""

    def get_supplier_phone(self, obj):
        return obj.supplier.supplier_phone if obj.supplier else ""

    def get_supplier_email(self, obj):
        return obj.supplier.supplier_email if obj.supplier else ""


class StockLossItemSerializer(serializers.Serializer):
    medicine_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class RegisterStockLossSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=[StockLoss.KIND_DAMAGED_WASTED], default=StockLoss.KIND_DAMAGED_WASTED)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    items = StockLossItemSerializer(many=True, allow_empty=False)


class StockLossSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField()
    expiry_date = serializers.SerializerMethodField()
    recorded_by = serializers.SerializerMethodField()

    def get_value(self, obj):
        return (Decimal(obj.quantity) * Decimal(obj.cost_price)).quantize(Decimal("0.01"))

    def get_expiry_date(self, obj):
        return obj.medicine.expiry_date if obj.medicine else None

    def get_recorded_by(self, obj):
        return obj.created_by.username if obj.created_by else ""

    class Meta:
        model = StockLoss
        fields = [
            "id",
            "medicine_id",
            "medicine_name",
            "batch_number",
            "kind",
            "quantity",
            "cost_price",
            "value",
            "expiry_date",
            "recorded_by",
            "note",
            "created_at",
        ]


class CreditPaymentSerializer(serializers.ModelSerializer):
    medicine_id = serializers.IntegerField(read_only=True)
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    batch_number = serializers.CharField(source="medicine.batch_number", read_only=True)
    supplier_name = serializers.SerializerMethodField()
    total_cost = serializers.SerializerMethodField()
    credit_amount = serializers.SerializerMethodField()
    recorded_by = serializers.SerializerMethodField()

    def get_supplier_name(self, obj):
        supplier = obj.medicine.supplier
        return supplier.supplier_name if supplier else ""

    def get_total_cost(self, obj):
        return (Decimal(obj.medicine.received_quantity) * Decimal(obj.medicine.cost)).quantize(Decimal("0.01"))

    def get_credit_amount(self, obj):
        owed = self.get_total_cost(obj) - Decimal(obj.medicine.paid_amount)
        return owed if owed > Decimal("0.01") else Decimal("0.00")

    def get_recorded_by(self, obj):
        return obj.created_by.username if obj.created_by else ""

    class Meta:
        model = CreditPayment
        fields = [
            "id",
            "medicine_id",
            "medicine_name",
            "batch_number",
            "supplier_name",
            "amount",
            "fully_paid",
            "total_cost",
            "credit_amount",
            "recorded_by",
            "created_at",
            "updated_at",
        ]
