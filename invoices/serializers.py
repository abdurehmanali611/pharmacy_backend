from rest_framework import serializers

from suppliers.models import Supplier

from .models import Invoice


class InvoiceSerializer(serializers.ModelSerializer):
    supplier_id = serializers.PrimaryKeyRelatedField(
        source="supplier",
        queryset=Supplier.objects.none(),
        allow_null=True,
        required=False,
        write_only=True,
    )
    selected_supplier_id = serializers.IntegerField(source="supplier.id", read_only=True)
    supplier_name = serializers.CharField(source="supplier.supplier_name", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "pharmacy_tin",
            "supplier_id",
            "selected_supplier_id",
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "invoice_amount",
            "invoice_status",
            "invoice_type",
            "invoice_payment_method",
            "invoice_image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "pharmacy_tin", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        pharmacy_tin = getattr(getattr(request, "user", None), "profile", None)
        pharmacy_tin = getattr(pharmacy_tin, "pharmacy_tin", "")
        self.fields["supplier_id"].queryset = Supplier.objects.filter(pharmacy_tin=pharmacy_tin)
