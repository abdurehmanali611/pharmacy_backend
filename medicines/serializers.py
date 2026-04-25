from rest_framework import serializers
from .models import Medicine

class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = [
            "id",
            "pharmacy_tin",
            "name",
            "price",
            "cost",
            "quantity",
            "description",
            "supplier_name",
            "supplier_phone",
            "supplier_email",
            "created_at",
            "updated_at"
        ]
        read_only_fields = ["id", "pharmacy_tin", "created_at", "updated_at"]