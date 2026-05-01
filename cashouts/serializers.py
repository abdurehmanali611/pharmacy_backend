from rest_framework import serializers

from .models import Cashout


class CashoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cashout
        fields = [
            "id",
            "pharmacy_tin",
            "amount",
            "reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "pharmacy_tin", "created_at", "updated_at"]

