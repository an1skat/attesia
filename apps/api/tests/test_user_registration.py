from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class UserRegistrationTest(APITestCase):
    def setUp(self):
        self.register_url = reverse("users:register")

        self.user_data = {
            "display_name": "test_user",
            "email": "test_first@example.com",
            "password": "VeryStrongPassword1234",
        }

    def test_successful_registration(self):
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertNotIn("password", response.data)
        self.assertEqual(response.data["email"], self.user_data["email"])
        self.assertEqual(response.data["display_name"], self.user_data["display_name"])

        user = User.objects.get(email=self.user_data["email"])
        self.assertEqual(user.display_name, self.user_data["display_name"])

        self.assertNotEqual(user.password, self.user_data["password"])
        self.assertTrue(user.check_password(self.user_data["password"]))

    def test_registration_missing_fields(self):
        incomplete_data = {"email": "test_second@example.com"}
        response = self.client.post(self.register_url, incomplete_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("display_name", response.data)
        self.assertIn("password", response.data)

    def test_registration_duplicate_email(self):
        User.objects.create_user(
            email=self.user_data["email"],
            display_name="test_display",
            password="password234",
        )

        response = self.client.post(self.register_url, self.user_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_registration_weak_password(self):
        weak_data = {
            "display_name": "weak_user",
            "email": "test_thirst@example.com",
            "password": "1234",
        }

        response = self.client.post(self.register_url, weak_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        self.assertTrue(len(response.data["password"]) > 0)
