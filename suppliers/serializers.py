from rest_framework import serializers

from .models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "pharmacy_tin",
            "supplier_name",
            "supplier_phone",
            "supplier_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "pharmacy_tin", "created_at", "updated_at"]

    def validate_supplier_name(self, value):
        supplier_name = (value or "").strip()
        if not supplier_name:
            raise serializers.ValidationError("Supplier name is required.")
        return supplier_name

