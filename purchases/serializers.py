from rest_framework import serializers
from .models import Purchase

class PurchaseSerializer(serializers.ModelSerializer):
    profit = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = [
            "id",
            "pharmacy_tin",
            "medicine_name",
            "quantity",
            "price",
            "cost_price",
            "total_price",
            "profit",
            "created_at",
            "updated_at"
        ]
        read_only_fields = ["id", "pharmacy_tin", "created_at", "updated_at"]

    def get_profit(self, obj):
        return obj.total_price - (obj.cost_price * obj.quantity)