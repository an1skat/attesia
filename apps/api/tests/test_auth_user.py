from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from app.modules.users.models import UserRefreshToken

User = get_user_model()

# Access login
# Login invalid credentials
# Refresh success
# Expired Refresh
# Refresh Invalid String


class AuthUser(APITestCase):
    def setUp(self):
        self.email = "test_first@example.com"
        self.password = "VeryStrongPassword1234"
        self.user = User.objects.create_user(
            email=self.email,
            password=self.password,
        )
        self.login_url = reverse("users:token_obtain")
        self.refresh_url = reverse("users:token_refresh")

    def test_login_success(self):
        data = {"email": self.email, "password": self.password}
        response = self.client.post(self.login_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        refresh_token_str = response.data["refresh"]
        self.assertTrue(
            UserRefreshToken.objects.filter(
                token=refresh_token_str, user=self.user
            ).exists()
        )

        try:
            AccessToken(response.data["access"])
        except Exception:
            self.fail("Access token is not valid JWT")

    def test_login_invalid_credentials(self):
        data = {"email": self.email, "password": "wrongPassword"}
        response = self.client.post(self.login_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_refresh_success(self):
        old_refresh_obj = UserRefreshToken.objects.create(user=self.user)
        old_token_str = old_refresh_obj.token

        data = {"refresh": old_token_str}
        response = self.client.post(self.refresh_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        self.assertFalse(
            UserRefreshToken.objects.filter(
                token=old_token_str,
            ).exists()
        )

        new_token_str = response.data["refresh"]
        self.assertTrue(
            UserRefreshToken.objects.filter(
                token=new_token_str,
                user=self.user,
            ).exists()
        )

    def test_token_refresh_expired(self):
        expired_date = timezone.now() - timedelta(days=1)
        refresh_obj = UserRefreshToken.objects.create(
            user=self.user, expires_at=expired_date
        )

        data = {"refresh": refresh_obj.token}
        response = self.client.post(self.refresh_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            UserRefreshToken.objects.filter(
                token=refresh_obj.token,
            ).exists()
        )

    def test_token_refresh_invalid_string(self):
        data = {"refresh": "some_random_string"}
        response = self.client.post(self.refresh_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
