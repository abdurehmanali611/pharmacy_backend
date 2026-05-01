from rest_framework import serializers

from suppliers.models import Supplier

from .models import Medicine

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
            "batch_number",
            "expiry_date",
            "description",
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
        return attrs

    def get_supplier_name(self, obj):
        return obj.supplier.supplier_name if obj.supplier else ""

    def get_supplier_phone(self, obj):
        return obj.supplier.supplier_phone if obj.supplier else ""

    def get_supplier_email(self, obj):
        return obj.supplier.supplier_email if obj.supplier else ""
