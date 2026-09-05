import hashlib
import secrets
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from app.modules.users.models import UserRefreshToken

User = get_user_model()


class AuthAPITestCase(APITestCase):
    def setUp(self):
        self.email = "test@example.com"
        self.password = "VeryStrongPassword1234!"
        self.display_name = "Test User"

        self.user = User.objects.create_user(
            email=self.email,
            password=self.password,
            display_name=self.display_name,
        )

        # self.register_url = reverse("users:register")
        self.login_url = reverse("users:token_obtain")
        self.refresh_url = reverse("users:token_refresh")

    def _create_refresh_token(self, user=None, **kwargs):
        user = user or self.user
        raw_token = secrets.token_urlsafe(32)
        hashed = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        kwargs.setdefault("family_id", uuid.uuid4())
        kwargs.setdefault("expires_at", timezone.now() + timedelta(days=30))

        obj = UserRefreshToken.objects.create(user=user, token_hash=hashed, **kwargs)
        return raw_token, obj

    # def test_register_success(self):
    #     data = {
    #         "email": "newuser@example.com",
    #         "display_name": "New User",
    #         "password": "VeryStrongPassword1234!"
    #     }
    #     response = self.client.post(self.register_url, data, format="json")
    #
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    #     self.assertIn("id", response.data)
    #     self.assertEqual(response.data["email"], data["email"])
    #     self.assertEqual(response.data["display_name"], data["display_name"])
    #     self.assertNotIn("password", response.data)
    #     self.assertTrue(User.objects.filter(email=data["email"]).exists())

    # def test_register_weak_password(self):
    #     data = {
    #         "email": "newuser2@example.com",
    #         "display_name": "New User",
    #         "password": "123"
    #     }
    #     response = self.client.post(self.register_url, data, format="json")
    #
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #     self.assertIn("password", response.data)

    # def test_register_duplicate_email(self):
    #     data = {
    #         "email": self.email,
    #         "display_name": "Another User",
    #         "password": "VeryStrongPassword1234!"
    #     }
    #     response = self.client.post(self.register_url, data, format="json")
    #
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #     self.assertIn("email", response.data)

    def test_login_success(self):
        data = {"email": self.email, "password": self.password}
        response = self.client.post(self.login_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)

        self.assertIn("refresh_token", response.cookies)
        cookie = response.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

        refresh_token_str = cookie.value
        hashed_token = hashlib.sha256(refresh_token_str.encode("utf-8")).hexdigest()

        self.assertTrue(
            UserRefreshToken.objects.filter(
                token_hash=hashed_token, user=self.user
            ).exists()
        )
        try:
            AccessToken(response.data["access"])
        except Exception:
            self.fail("Access token is not a valid JWT")

    def test_login_invalid_credentials(self):
        data = {"email": self.email, "password": "wrongPassword123!"}
        response = self.client.post(self.login_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

    def test_login_missing_fields(self):
        data = {"email": self.email}
        response = self.client.post(self.login_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_success(self):
        raw_token, old_refresh_obj = self._create_refresh_token()

        self.client.cookies["refresh_token"] = raw_token
        response = self.client.post(self.refresh_url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)

        old_refresh_obj.refresh_from_db()
        self.assertIsNotNone(old_refresh_obj.revoked_at)

        self.assertIn("refresh_token", response.cookies)
        new_cookie = response.cookies["refresh_token"]
        self.assertNotEqual(new_cookie.value, raw_token)

        new_hashed = hashlib.sha256(new_cookie.value.encode("utf-8")).hexdigest()
        self.assertTrue(
            UserRefreshToken.objects.filter(
                token_hash=new_hashed, user=self.user
            ).exists()
        )

    def test_refresh_missing_cookie(self):
        response = self.client.post(self.refresh_url, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_text = str(response.data).lower()
        self.assertTrue("missing" in response_text or "refresh" in response_text)

    def test_refresh_invalid_string(self):
        self.client.cookies["refresh_token"] = "some_random_invalid_string"
        response = self.client.post(self.refresh_url, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_text = str(response.data).lower()
        self.assertTrue("invalid" in response_text or "refresh" in response_text)

    def test_refresh_expired_token(self):
        expired_date = timezone.now() - timedelta(days=1)
        raw_token, refresh_obj = self._create_refresh_token(expires_at=expired_date)

        self.client.cookies["refresh_token"] = raw_token
        response = self.client.post(self.refresh_url, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        refresh_obj.refresh_from_db()
        self.assertIsNotNone(refresh_obj.revoked_at)
        self.assertTrue("expired" in str(response.data).lower())

    def test_refresh_token_reuse_detection_triggers_family_revocation(self):
        family_id = uuid.uuid4()

        raw_token_1, token_1 = self._create_refresh_token(
            family_id=family_id,
            revoked_at=timezone.now(),
        )
        raw_token_2, token_2 = self._create_refresh_token(
            family_id=family_id,
        )

        self.client.cookies["refresh_token"] = raw_token_1
        response = self.client.post(self.refresh_url, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_text = str(response.data).lower()
        self.assertTrue(
            "revoked" in response_text
            or "compromised" in response_text
            or "family" in response_text
        )

        token_2.refresh_from_db()
        self.assertIsNotNone(token_2.revoked_at)
