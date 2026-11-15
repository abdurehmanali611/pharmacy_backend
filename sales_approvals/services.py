from decimal import Decimal

from django.db import transaction
from django.db.models import Case, F, IntegerField, Value, When
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from medicines.models import Medicine
from purchases.models import Purchase
from purchases.serializers import PurchaseSerializer

from .models import ApprovalRequiredMedicine, PendingSale, PendingSaleLine, QuantitySaleRule


def get_pharmacy_tin(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "pharmacy_tin", "") or ""


def get_medicine_for_pharmacy(medicine_name, pharmacy_tin, medicine_id=None):
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


def validate_not_expired(medicine):
    if medicine.expiry_date and medicine.expiry_date < timezone.localdate():
        raise ValidationError(
            {"medicine_name": [f"{medicine.name}: Expired stock cannot be sold."]}
        )


def quantity_in_band(quantity, threshold, final):
    if quantity < threshold:
        return False
    if final is not None and quantity > final:
        return False
    return True


def get_quantity_rule(pharmacy_tin, medicine):
    return QuantitySaleRule.objects.filter(
        pharmacy_tin=pharmacy_tin, medicine=medicine
    ).first()


def quantity_exceeds_final(quantity, rule):
    """Rule 1 with a final cap: qty above final is auto-rejected."""
    return bool(rule and rule.final is not None and quantity > rule.final)


def evaluate_item_trigger(pharmacy_tin, medicine, quantity):
    if ApprovalRequiredMedicine.objects.filter(
        pharmacy_tin=pharmacy_tin, medicine=medicine
    ).exists():
        return PendingSaleLine.TRIGGER_NEEDS_APPROVAL

    rule = get_quantity_rule(pharmacy_tin, medicine)
    if rule and quantity_exceeds_final(quantity, rule):
        return PendingSaleLine.TRIGGER_NONE
    if rule and quantity_in_band(quantity, rule.threshold, rule.final):
        return PendingSaleLine.TRIGGER_QUANTITY_BAND

    return PendingSaleLine.TRIGGER_NONE


def find_auto_rejected_items(pharmacy_tin, resolved_items):
    """
    Rule 1 items requested above final are auto-rejected.
    Returns list of human-readable rejection messages.
    """
    messages = []
    for item in resolved_items:
        medicine = item["medicine"]
        quantity = item["quantity"]
        rule = get_quantity_rule(pharmacy_tin, medicine)
        if quantity_exceeds_final(quantity, rule):
            messages.append(
                f"{item['medicine_name']}: quantity {quantity} exceeds the allowed "
                f"maximum of {rule.final}. Sale auto-rejected."
            )
    return messages


def cart_requires_approval(pharmacy_tin, resolved_items):
    """resolved_items: list of dicts with medicine, quantity."""
    for item in resolved_items:
        trigger = evaluate_item_trigger(pharmacy_tin, item["medicine"], item["quantity"])
        if trigger != PendingSaleLine.TRIGGER_NONE:
            return True
    return False


def create_pending_sale(user, pharmacy_tin, resolved_items):
    with transaction.atomic():
        pending = PendingSale.objects.create(
            pharmacy_tin=pharmacy_tin,
            status=PendingSale.STATUS_AWAITING_MANAGER,
            created_by=user,
        )
        for item in resolved_items:
            medicine = item["medicine"]
            quantity = item["quantity"]
            trigger = evaluate_item_trigger(pharmacy_tin, medicine, quantity)
            PendingSaleLine.objects.create(
                pending_sale=pending,
                medicine=medicine,
                medicine_name=item["medicine_name"],
                original_quantity=quantity,
                original_price=item["price"],
                trigger=trigger,
                is_attachment=False,
            )
        return pending


def ensure_mutual_exclusion(pharmacy_tin, medicine_ids, for_rule):
    medicine_ids = list({int(mid) for mid in medicine_ids})
    if for_rule == "quantity":
        conflict = ApprovalRequiredMedicine.objects.filter(
            pharmacy_tin=pharmacy_tin, medicine_id__in=medicine_ids
        ).select_related("medicine")
        if conflict.exists():
            names = ", ".join(c.medicine.name for c in conflict)
            raise ValidationError(
                {
                    "medicine_id": [
                        f"Already marked Needs Approval: {names}. Remove that rule first."
                    ]
                }
            )
    elif for_rule == "approval":
        conflict = QuantitySaleRule.objects.filter(
            pharmacy_tin=pharmacy_tin, medicine_id__in=medicine_ids
        ).select_related("medicine")
        if conflict.exists():
            names = ", ".join(c.medicine.name for c in conflict)
            raise ValidationError(
                {
                    "medicine_id": [
                        f"Already has a quantity band: {names}. Remove that rule first."
                    ]
                }
            )


def settle_pending_sale(pending: PendingSale):
    """Create purchases from pharmacist-confirmed lines. Inventory decremented here."""
    if pending.status != PendingSale.STATUS_AWAITING_PHARMACIST:
        raise ValidationError({"detail": "Sale is not awaiting pharmacist confirmation."})

    lines = list(
        pending.lines.select_related("medicine").filter(
            pharmacist_quantity__isnull=False
        )
    )
    if not lines:
        raise ValidationError({"detail": "No confirmed line quantities to settle."})

    pharmacy_tin = pending.pharmacy_tin
    created_purchases = []

    with transaction.atomic():
        medicine_ids = [line.medicine_id for line in lines if line.medicine_id]
        locked = {
            m.pk: m
            for m in Medicine.objects.select_for_update().filter(
                pharmacy_tin=pharmacy_tin, pk__in=medicine_ids
            )
        }

        for line in lines:
            qty = line.pharmacist_quantity
            if qty is None or qty <= 0:
                raise ValidationError(
                    {"items": [f"{line.medicine_name}: Confirmed quantity is required."]}
                )

            # Attachments and rule-2 bands require pharmacist qty inside manager band.
            needs_band = line.is_attachment or line.trigger == PendingSaleLine.TRIGGER_NEEDS_APPROVAL
            if needs_band:
                if line.qty_threshold is None:
                    raise ValidationError(
                        {"items": [f"{line.medicine_name}: Manager quantity band is missing."]}
                    )
                if not quantity_in_band(qty, line.qty_threshold, line.qty_final):
                    band = (
                        f">={line.qty_threshold}"
                        if line.qty_final is None
                        else f"{line.qty_threshold}-{line.qty_final}"
                    )
                    raise ValidationError(
                        {"items": [f"{line.medicine_name}: Quantity must be within {band}."]}
                    )
            elif line.trigger == PendingSaleLine.TRIGGER_QUANTITY_BAND:
                # Keep original cart qty unless pharmacist overrode (same band check optional)
                pass

            medicine = locked.get(line.medicine_id) if line.medicine_id else None
            if medicine is None and not line.is_attachment:
                raise ValidationError(
                    {"items": [f"{line.medicine_name}: Medicine not found in inventory."]}
                )

            price = line.effective_price()
            cost_price = medicine.cost if medicine else Decimal("0.00")

            # Attachments: no stock requirement. Regular lines: decrement inventory.
            if line.is_attachment:
                pass
            elif medicine is not None:
                validate_not_expired(medicine)
                if medicine.quantity < qty:
                    raise ValidationError(
                        {
                            "items": [
                                f"{medicine.name}: Insufficient stock. Available: {medicine.quantity}."
                            ]
                        }
                    )
                medicine.quantity = medicine.quantity - qty
                medicine.save(update_fields=["quantity"])

            purchase = Purchase.objects.create(
                pharmacy_tin=pharmacy_tin,
                medicine=medicine if not line.is_attachment else medicine,
                medicine_name=line.medicine_name,
                quantity=qty,
                price=price,
                total_price=Decimal(qty) * Decimal(price),
                cost_price=cost_price,
            )
            created_purchases.append(purchase)

        pending.status = PendingSale.STATUS_SETTLED
        pending.save(update_fields=["status", "updated_at"])

    return PurchaseSerializer(created_purchases, many=True).data
