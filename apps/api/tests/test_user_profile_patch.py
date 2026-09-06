from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


class UserProfilePatchTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profile_test@example.com",
            password="StrongPassword123!",
            display_name="Original Name",
        )
        self.profile_url = reverse("users:user_profile")
        self.token = str(AccessToken.for_user(self.user))

    def test_patch_display_name_success(self):
        payload = {"display_name": "Updated Name"}
        response = self.client.patch(
            self.profile_url,
            data=payload,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["display_name"], payload["display_name"])
        self.assertEqual(response.data["email"], self.user.email)

        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, payload["display_name"])

    def test_patch_email_normalization(self):
        payload = {"email": "testuser@EXAMPLE.COM"}

        response = self.client.patch(
            self.profile_url,
            data=payload,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "testuser@example.com")

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "testuser@example.com")

    def test_patch_read_only_fields_ignored(self):
        payload = {
            "display_name": "New Name",
            "is_active": False,
            "id": 99999,
        }
        response = self.client.patch(
            self.profile_url,
            data=payload,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["display_name"], "New Name")

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertNotEqual(self.user.id, 99999)

    def test_patch_invalid_email_format(self):
        payload = {"email": "not-an-email"}
        response = self.client.patch(
            self.profile_url,
            data=payload,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_patch_duplicate_email_case_insensitive(self):
        User.objects.create_user(
            email="occupied@example.com",
            password="StrongPassword123!",
            display_name="Other User",
        )

        payload = {"email": "occupied@EXAMPLE.COM"}
        response = self.client.patch(
            self.profile_url,
            data=payload,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_patch_unauthorized(self):
        payload = {"display_name": "New Name"}
        response = self.client.patch(
            self.profile_url,
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
