from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .serializers import MedicineSerializer


class MedicineSerializerImageUrlTests(SimpleTestCase):
    def setUp(self):
        self.image_url_field = MedicineSerializer().fields["image_url"]

    def test_image_url_is_optional_and_accepts_null_or_blank(self):
        self.assertFalse(self.image_url_field.required)
        self.assertTrue(self.image_url_field.allow_null)
        self.assertTrue(self.image_url_field.allow_blank)
        self.assertEqual(self.image_url_field.run_validation(None), None)
        self.assertEqual(self.image_url_field.run_validation(""), "")

    def test_image_url_accepts_valid_url(self):
        image_url = "https://res.cloudinary.com/example/image/upload/medicine.jpg"

        self.assertEqual(self.image_url_field.run_validation(image_url), image_url)

    def test_image_url_rejects_invalid_url(self):
        with self.assertRaises(ValidationError):
            self.image_url_field.run_validation("not-a-url")
