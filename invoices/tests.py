from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .serializers import InvoiceSerializer


class InvoicePaymentMethodTests(SimpleTestCase):
    def setUp(self):
        self.payment_method_field = InvoiceSerializer().fields["invoice_payment_method"]

    def test_telebirr_is_a_valid_payment_method(self):
        self.assertEqual(self.payment_method_field.run_validation("Telebirr"), "Telebirr")

    def test_unknown_payment_method_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.payment_method_field.run_validation("Unknown")
