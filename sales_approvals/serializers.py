from rest_framework import serializers

from medicines.models import Medicine

from .models import (
    ApprovalRequiredMedicine,
    PendingSale,
    PendingSaleLine,
    QuantitySaleRule,
)
class QuantitySaleRuleSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_id = serializers.PrimaryKeyRelatedField(
        source="medicine", queryset=Medicine.objects.all()
    )

    class Meta:
        model = QuantitySaleRule
        fields = [
            "id",
            "pharmacy_tin",
            "medicine_id",
            "medicine_name",
            "threshold",
            "final",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "pharmacy_tin", "medicine_name", "created_at", "updated_at"]

    def validate(self, attrs):
        threshold = attrs.get("threshold", getattr(self.instance, "threshold", None))
        final = attrs.get("final", getattr(self.instance, "final", None))
        if threshold is None or threshold < 1:
            raise serializers.ValidationError({"threshold": "Threshold must be at least 1."})
        if final is not None and final < threshold:
            raise serializers.ValidationError(
                {"final": "Final must be greater than or equal to threshold."}
            )
        return attrs


class BulkQuantitySaleRuleItemSerializer(serializers.Serializer):
    medicine_id = serializers.IntegerField()
    threshold = serializers.IntegerField(min_value=1)
    final = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate(self, attrs):
        threshold = attrs.get("threshold")
        final = attrs.get("final")
        if final is not None and threshold is not None and final < threshold:
            raise serializers.ValidationError(
                {"final": "Final must be greater than or equal to threshold."}
            )
        return attrs


class BulkQuantitySaleRuleSerializer(serializers.Serializer):
    items = BulkQuantitySaleRuleItemSerializer(many=True)


class ApprovalRequiredMedicineSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_price = serializers.DecimalField(
        source="medicine.price", max_digits=10, decimal_places=2, read_only=True
    )
    medicine_quantity = serializers.IntegerField(source="medicine.quantity", read_only=True)
    medicine_id = serializers.PrimaryKeyRelatedField(
        source="medicine", queryset=Medicine.objects.all()
    )

    class Meta:
        model = ApprovalRequiredMedicine
        fields = [
            "id",
            "pharmacy_tin",
            "medicine_id",
            "medicine_name",
            "medicine_price",
            "medicine_quantity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "pharmacy_tin",
            "medicine_name",
            "medicine_price",
            "medicine_quantity",
            "created_at",
            "updated_at",
        ]


class BulkApprovalRequiredSerializer(serializers.Serializer):
    medicine_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False
    )


class PendingSaleLineSerializer(serializers.ModelSerializer):
    medicine_id = serializers.IntegerField(read_only=True, allow_null=True)
    effective_price = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = PendingSaleLine
        fields = [
            "id",
            "medicine_id",
            "medicine_name",
            "original_quantity",
            "original_price",
            "trigger",
            "is_attachment",
            "parent_line",
            "manager_unit_price",
            "qty_threshold",
            "qty_final",
            "pharmacist_quantity",
            "effective_price",
            "attachments",
            "created_at",
            "updated_at",
        ]

    def get_effective_price(self, obj):
        return obj.effective_price()

    def get_attachments(self, obj):
        if obj.is_attachment:
            return []
        kids = obj.attachments.all()
        return PendingSaleLineSerializer(kids, many=True).data


class PendingSaleSerializer(serializers.ModelSerializer):
    lines = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True, default=""
    )

    class Meta:
        model = PendingSale
        fields = [
            "id",
            "pharmacy_tin",
            "status",
            "created_by",
            "created_by_username",
            "reviewed_by",
            "manager_reject_reason",
            "lines",
            "created_at",
            "updated_at",
        ]

    def get_lines(self, obj):
        roots = obj.lines.filter(is_attachment=False)
        return PendingSaleLineSerializer(roots, many=True).data


class ManagerLineUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    manager_unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    qty_threshold = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    qty_final = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate(self, attrs):
        threshold = attrs.get("qty_threshold")
        final = attrs.get("qty_final")
        if final is not None and threshold is not None and final < threshold:
            raise serializers.ValidationError(
                {"qty_final": "Final must be greater than or equal to threshold."}
            )
        return attrs


class ManagerAttachmentSerializer(serializers.Serializer):
    parent_line_id = serializers.IntegerField()
    medicine_id = serializers.IntegerField(required=False, allow_null=True)
    medicine_name = serializers.CharField(max_length=255)
    qty_threshold = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    qty_final = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    manager_unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    original_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0
    )

    def validate(self, attrs):
        threshold = attrs.get("qty_threshold")
        final = attrs.get("qty_final")
        if final is not None and threshold is not None and final < threshold:
            raise serializers.ValidationError(
                {"qty_final": "Final must be greater than or equal to threshold."}
            )
        return attrs


class ManagerDecideSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    reject_reason = serializers.CharField(required=False, allow_blank=True)
    line_updates = ManagerLineUpdateSerializer(many=True, required=False)
    attachments = ManagerAttachmentSerializer(many=True, required=False)


class PharmacistConfirmLineSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class PharmacistConfirmSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["accept", "reject"])
    lines = PharmacistConfirmLineSerializer(many=True, required=False)
