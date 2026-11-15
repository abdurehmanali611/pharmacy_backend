from decimal import Decimal

from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from medicines.models import Medicine

from .models import (
    ApprovalRequiredMedicine,
    PendingSale,
    PendingSaleLine,
    QuantitySaleRule,
)
from .serializers import (
    ApprovalRequiredMedicineSerializer,
    BulkApprovalRequiredSerializer,
    BulkQuantitySaleRuleSerializer,
    ManagerDecideSerializer,
    PendingSaleSerializer,
    PharmacistConfirmSerializer,
    QuantitySaleRuleSerializer,
)
from .services import (
    ensure_mutual_exclusion,
    get_pharmacy_tin,
    get_quantity_rule,
    quantity_in_band,
    settle_pending_sale,
)


class QuantitySaleRuleViewSet(viewsets.ModelViewSet):
    serializer_class = QuantitySaleRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tin = get_pharmacy_tin(self.request.user)
        if not tin:
            return QuantitySaleRule.objects.none()
        return QuantitySaleRule.objects.filter(pharmacy_tin=tin).select_related("medicine")

    def perform_create(self, serializer):
        tin = get_pharmacy_tin(self.request.user)
        if not tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})
        medicine = serializer.validated_data["medicine"]
        if medicine.pharmacy_tin != tin:
            raise ValidationError({"medicine_id": ["Medicine not found in this pharmacy."]})
        ensure_mutual_exclusion(tin, [medicine.pk], "quantity")
        serializer.save(pharmacy_tin=tin)

    def perform_update(self, serializer):
        tin = get_pharmacy_tin(self.request.user)
        medicine = serializer.validated_data.get("medicine", serializer.instance.medicine)
        if medicine.pharmacy_tin != tin:
            raise ValidationError({"medicine_id": ["Medicine not found in this pharmacy."]})
        ensure_mutual_exclusion(tin, [medicine.pk], "quantity")
        serializer.save(pharmacy_tin=tin)

    @action(detail=False, methods=["post"], url_path="bulk_create")
    def bulk_create(self, request):
        tin = get_pharmacy_tin(request.user)
        if not tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})

        serializer = BulkQuantitySaleRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data["items"]
        if not items:
            raise ValidationError({"items": ["Add at least one rule."]})

        medicine_ids = [item["medicine_id"] for item in items]
        if len(medicine_ids) != len(set(medicine_ids)):
            raise ValidationError({"items": ["Each medicine can only appear once in the batch."]})

        ensure_mutual_exclusion(tin, medicine_ids, "quantity")

        existing = set(
            QuantitySaleRule.objects.filter(
                pharmacy_tin=tin, medicine_id__in=medicine_ids
            ).values_list("medicine_id", flat=True)
        )
        if existing:
            raise ValidationError(
                {"items": [f"Medicine id(s) already have quantity rules: {sorted(existing)}"]}
            )

        medicines = {
            m.pk: m
            for m in Medicine.objects.filter(pharmacy_tin=tin, pk__in=medicine_ids)
        }
        if len(medicines) != len(medicine_ids):
            raise ValidationError({"items": ["One or more medicines were not found."]})

        created = []
        with transaction.atomic():
            for item in items:
                final = item.get("final")
                threshold = item["threshold"]
                if final is not None and final < threshold:
                    raise ValidationError(
                        {
                            "items": [
                                f"{medicines[item['medicine_id']].name}: final must be ≥ threshold."
                            ]
                        }
                    )
                created.append(
                    QuantitySaleRule.objects.create(
                        pharmacy_tin=tin,
                        medicine=medicines[item["medicine_id"]],
                        threshold=threshold,
                        final=final,
                    )
                )

        return Response(
            QuantitySaleRuleSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class ApprovalRequiredMedicineViewSet(viewsets.ModelViewSet):
    serializer_class = ApprovalRequiredMedicineSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        tin = get_pharmacy_tin(self.request.user)
        if not tin:
            return ApprovalRequiredMedicine.objects.none()
        return ApprovalRequiredMedicine.objects.filter(
            pharmacy_tin=tin
        ).select_related("medicine")

    def perform_create(self, serializer):
        tin = get_pharmacy_tin(self.request.user)
        if not tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})
        medicine = serializer.validated_data["medicine"]
        if medicine.pharmacy_tin != tin:
            raise ValidationError({"medicine_id": ["Medicine not found in this pharmacy."]})
        ensure_mutual_exclusion(tin, [medicine.pk], "approval")
        serializer.save(pharmacy_tin=tin)

    @action(detail=False, methods=["post"], url_path="bulk_create")
    def bulk_create(self, request):
        tin = get_pharmacy_tin(request.user)
        if not tin:
            raise ValidationError({"detail": "Missing pharmacy TIN for the current user."})

        serializer = BulkApprovalRequiredSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        medicine_ids = list(dict.fromkeys(serializer.validated_data["medicine_ids"]))

        ensure_mutual_exclusion(tin, medicine_ids, "approval")

        existing = set(
            ApprovalRequiredMedicine.objects.filter(
                pharmacy_tin=tin, medicine_id__in=medicine_ids
            ).values_list("medicine_id", flat=True)
        )
        to_create = [mid for mid in medicine_ids if mid not in existing]
        medicines = {
            m.pk: m for m in Medicine.objects.filter(pharmacy_tin=tin, pk__in=to_create)
        }
        if len(medicines) != len(to_create):
            raise ValidationError({"medicine_ids": ["One or more medicines were not found."]})

        created = [
            ApprovalRequiredMedicine(pharmacy_tin=tin, medicine=medicines[mid])
            for mid in to_create
        ]
        ApprovalRequiredMedicine.objects.bulk_create(created)
        qs = ApprovalRequiredMedicine.objects.filter(
            pharmacy_tin=tin, medicine_id__in=medicine_ids
        ).select_related("medicine")
        return Response(
            ApprovalRequiredMedicineSerializer(qs, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class PendingSaleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PendingSaleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tin = get_pharmacy_tin(self.request.user)
        if not tin:
            return PendingSale.objects.none()
        qs = PendingSale.objects.filter(pharmacy_tin=tin).prefetch_related(
            "lines__attachments", "lines__medicine", "created_by"
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    @action(detail=True, methods=["post"], url_path="manager_decide")
    def manager_decide(self, request, pk=None):
        tin = get_pharmacy_tin(request.user)
        pending = self.get_object()
        if pending.pharmacy_tin != tin:
            raise ValidationError({"detail": "Not found."})
        if pending.status != PendingSale.STATUS_AWAITING_MANAGER:
            raise ValidationError({"detail": "This sale is not awaiting manager action."})

        serializer = ManagerDecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        action_name = data["action"]

        if action_name == "reject":
            reason = (data.get("reject_reason") or "").strip()
            if not reason:
                raise ValidationError({"reject_reason": ["A reject reason is required."]})
            pending.status = PendingSale.STATUS_REJECTED
            pending.manager_reject_reason = reason
            pending.reviewed_by = request.user
            pending.save(
                update_fields=[
                    "status",
                    "manager_reject_reason",
                    "reviewed_by",
                    "updated_at",
                ]
            )
            return Response(PendingSaleSerializer(pending).data)

        # approve (as-is or with updates)
        line_updates = {u["id"]: u for u in data.get("line_updates") or []}
        attachments = data.get("attachments") or []

        with transaction.atomic():
            root_lines = {
                line.id: line
                for line in pending.lines.select_for_update().filter(is_attachment=False)
            }

            for line_id, update in line_updates.items():
                line = root_lines.get(line_id) or pending.lines.filter(pk=line_id).first()
                if not line or line.pending_sale_id != pending.id:
                    raise ValidationError({"line_updates": [f"Unknown line {line_id}."]})

                if "manager_unit_price" in update:
                    line.manager_unit_price = update["manager_unit_price"]

                # Rule 2 lines need a qty band for pharmacist entry.
                if line.trigger == PendingSaleLine.TRIGGER_NEEDS_APPROVAL:
                    threshold = update.get("qty_threshold")
                    final = update.get("qty_final")
                    if threshold is None:
                        # approve as-is: lock band to original quantity
                        threshold = line.original_quantity
                        final = line.original_quantity
                    if final is not None and final < threshold:
                        raise ValidationError(
                            {
                                "line_updates": [
                                    f"{line.medicine_name}: final must be ≥ threshold."
                                ]
                            }
                        )
                    line.qty_threshold = threshold
                    line.qty_final = final
                elif "qty_threshold" in update or "qty_final" in update:
                    threshold = update.get("qty_threshold", line.qty_threshold)
                    final = update.get("qty_final", line.qty_final)
                    if threshold is not None and final is not None and final < threshold:
                        raise ValidationError(
                            {"line_updates": [f"{line.medicine_name}: final must be ≥ threshold."]}
                        )
                    if "qty_threshold" in update:
                        line.qty_threshold = threshold
                    if "qty_final" in update:
                        line.qty_final = final

                line.save()

            # Default bands for any rule-2 line not explicitly updated
            for line in root_lines.values():
                if (
                    line.trigger == PendingSaleLine.TRIGGER_NEEDS_APPROVAL
                    and line.qty_threshold is None
                ):
                    line.qty_threshold = line.original_quantity
                    line.qty_final = line.original_quantity
                    line.save(update_fields=["qty_threshold", "qty_final", "updated_at"])

            for attachment in attachments:
                parent = root_lines.get(attachment["parent_line_id"])
                if not parent:
                    raise ValidationError(
                        {
                            "attachments": [
                                f"Unknown parent line {attachment['parent_line_id']}."
                            ]
                        }
                    )

                medicine = None
                medicine_id = attachment.get("medicine_id")
                if medicine_id:
                    medicine = Medicine.objects.filter(
                        pharmacy_tin=tin, pk=medicine_id
                    ).first()

                # Rule 1 attachments: band comes from the quantity rule; only unit price is editable.
                rule = get_quantity_rule(tin, medicine) if medicine else None
                if rule:
                    threshold = rule.threshold
                    final = rule.final
                else:
                    threshold = attachment.get("qty_threshold")
                    final = attachment.get("qty_final")
                    if threshold is None:
                        raise ValidationError(
                            {
                                "attachments": [
                                    f"{attachment['medicine_name']}: quantity threshold is required."
                                ]
                            }
                        )
                    if final is not None and final < threshold:
                        raise ValidationError(
                            {
                                "attachments": [
                                    f"{attachment['medicine_name']}: final must be ≥ threshold."
                                ]
                            }
                        )

                original_price = attachment.get("original_price")
                if original_price is None:
                    original_price = medicine.price if medicine else Decimal("0.00")

                PendingSaleLine.objects.create(
                    pending_sale=pending,
                    medicine=medicine,
                    medicine_name=attachment["medicine_name"],
                    original_quantity=threshold,
                    original_price=original_price,
                    trigger=PendingSaleLine.TRIGGER_NONE,
                    is_attachment=True,
                    parent_line=parent,
                    manager_unit_price=attachment.get("manager_unit_price"),
                    qty_threshold=threshold,
                    qty_final=final,
                )

            pending.status = PendingSale.STATUS_AWAITING_PHARMACIST
            pending.reviewed_by = request.user
            pending.save(update_fields=["status", "reviewed_by", "updated_at"])

        pending.refresh_from_db()
        return Response(PendingSaleSerializer(pending).data)

    @action(detail=True, methods=["post"], url_path="pharmacist_confirm")
    def pharmacist_confirm(self, request, pk=None):
        tin = get_pharmacy_tin(request.user)
        pending = self.get_object()
        if pending.pharmacy_tin != tin:
            raise ValidationError({"detail": "Not found."})

        serializer = PharmacistConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if pending.status == PendingSale.STATUS_REJECTED:
            # Acknowledge manager rejection → mark failed/closed for pharmacist inbox
            if data["action"] == "reject":
                pending.status = PendingSale.STATUS_FAILED
                pending.save(update_fields=["status", "updated_at"])
                return Response(PendingSaleSerializer(pending).data)
            raise ValidationError(
                {"detail": "Manager rejected this sale. Dismiss it or start a new sale."}
            )

        if pending.status != PendingSale.STATUS_AWAITING_PHARMACIST:
            raise ValidationError({"detail": "This sale is not awaiting pharmacist confirmation."})

        if data["action"] == "reject":
            pending.status = PendingSale.STATUS_FAILED
            pending.save(update_fields=["status", "updated_at"])
            return Response(PendingSaleSerializer(pending).data)

        confirmations = {item["id"]: item["quantity"] for item in data.get("lines") or []}
        lines = list(pending.lines.select_related("medicine").all())
        if not lines:
            raise ValidationError({"detail": "No lines on this pending sale."})

        for line in lines:
            needs_qty = (
                line.is_attachment
                or line.trigger == PendingSaleLine.TRIGGER_NEEDS_APPROVAL
                or line.id in confirmations
            )
            if line.trigger == PendingSaleLine.TRIGGER_QUANTITY_BAND and line.id not in confirmations:
                # default to original quantity
                line.pharmacist_quantity = line.original_quantity
                line.save(update_fields=["pharmacist_quantity", "updated_at"])
                continue

            if line.trigger == PendingSaleLine.TRIGGER_NONE and not line.is_attachment:
                if line.id not in confirmations:
                    line.pharmacist_quantity = line.original_quantity
                    line.save(update_fields=["pharmacist_quantity", "updated_at"])
                    continue

            qty = confirmations.get(line.id)
            if qty is None:
                if needs_qty and (
                    line.is_attachment
                    or line.trigger == PendingSaleLine.TRIGGER_NEEDS_APPROVAL
                ):
                    raise ValidationError(
                        {"lines": [f"{line.medicine_name}: Enter a quantity within the band."]}
                    )
                line.pharmacist_quantity = line.original_quantity
                line.save(update_fields=["pharmacist_quantity", "updated_at"])
                continue

            if line.qty_threshold is not None and not quantity_in_band(
                qty, line.qty_threshold, line.qty_final
            ):
                band = (
                    f">={line.qty_threshold}"
                    if line.qty_final is None
                    else f"{line.qty_threshold}-{line.qty_final}"
                )
                raise ValidationError(
                    {"lines": [f"{line.medicine_name}: Quantity must be within {band}."]}
                )

            line.pharmacist_quantity = qty
            line.save(update_fields=["pharmacist_quantity", "updated_at"])

        results = settle_pending_sale(pending)
        pending.refresh_from_db()
        return Response(
            {
                "detail": f"Recorded {len(results)} sale item(s).",
                "pending_sale": PendingSaleSerializer(pending).data,
                "results": results,
            },
            status=status.HTTP_201_CREATED,
        )
