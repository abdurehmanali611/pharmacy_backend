from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .views import BulkPurchaseItemSerializer, PurchaseViewSet


class PurchaseExpiryValidationTests(SimpleTestCase):
    def setUp(self):
        self.view = PurchaseViewSet()
        self.today = timezone.localdate()

    @patch("purchases.views.timezone.localdate")
    def test_rejects_medicine_expired_before_today(self, localdate):
        localdate.return_value = self.today
        medicine = SimpleNamespace(name="Example medicine", expiry_date=self.today - timedelta(days=1))

        with self.assertRaises(ValidationError):
            self.view._validate_not_expired(medicine)

    @patch("purchases.views.timezone.localdate")
    def test_allows_medicine_expiring_today(self, localdate):
        localdate.return_value = self.today
        medicine = SimpleNamespace(name="Example medicine", expiry_date=self.today)

        self.view._validate_not_expired(medicine)

    def test_bulk_purchase_accepts_an_exact_medicine_id(self):
        serializer = BulkPurchaseItemSerializer(
            data={
                "medicine_id": 42,
                "medicine_name": "Example medicine",
                "quantity": 1,
                "price": "12.50",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["medicine_id"], 42)

    @patch("purchases.views.Medicine.objects")
    def test_medicine_lookup_uses_the_selected_batch_id(self, medicine_objects):
        expected = SimpleNamespace(id=42)
        queryset = MagicMock()
        medicine_objects.filter.return_value = queryset
        queryset.filter.return_value.first.return_value = expected

        result = self.view._get_medicine_for_pharmacy("Example medicine", "TIN-1", 42)

        self.assertIs(result, expected)
        medicine_objects.filter.assert_called_once_with(pharmacy_tin="TIN-1")
        queryset.filter.assert_called_once_with(pk=42, name="Example medicine")
