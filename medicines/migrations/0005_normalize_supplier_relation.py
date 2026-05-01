from django.db import migrations


def attach_suppliers_to_medicines(apps, schema_editor):
    Medicine = apps.get_model("medicines", "Medicine")
    Supplier = apps.get_model("suppliers", "Supplier")

    for medicine in Medicine.objects.all().iterator():
        if medicine.supplier_id:
            continue

        supplier_name = (medicine.supplier_name or "").strip()
        supplier_phone = (medicine.supplier_phone or "").strip()
        supplier_email = (medicine.supplier_email or "").strip()

        if not supplier_name:
            continue

        supplier, _ = Supplier.objects.get_or_create(
            pharmacy_tin=medicine.pharmacy_tin,
            supplier_name=supplier_name,
            defaults={
                "supplier_phone": supplier_phone,
                "supplier_email": supplier_email,
            },
        )

        updated = False
        if supplier_phone and supplier.supplier_phone != supplier_phone:
            supplier.supplier_phone = supplier_phone
            updated = True
        if supplier_email != supplier.supplier_email:
            supplier.supplier_email = supplier_email
            updated = True
        if updated:
            supplier.save(update_fields=["supplier_phone", "supplier_email", "updated_at"])

        medicine.supplier_id = supplier.id
        medicine.save(update_fields=["supplier"])


class Migration(migrations.Migration):
    dependencies = [
        ("medicines", "0004_medicine_batch_number_supplier"),
    ]

    operations = [
        migrations.RunPython(attach_suppliers_to_medicines, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="medicine",
            name="supplier_email",
        ),
        migrations.RemoveField(
            model_name="medicine",
            name="supplier_name",
        ),
        migrations.RemoveField(
            model_name="medicine",
            name="supplier_phone",
        ),
    ]
