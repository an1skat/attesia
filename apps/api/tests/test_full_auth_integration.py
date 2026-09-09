from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from app.modules.users.models import (
    UserRefreshToken,  # Укажите вашу модель токена/сессии
)
from app.modules.users.services import UserService

User = get_user_model()


class AuthFullIntegrationTestCase(APITestCase):
    def setUp(self):
        self.register_url = reverse("users:user_register")
        self.login_url = reverse("users:token_obtain")
        self.me_url = reverse("users:user_profile")
        self.refresh_url = reverse("users:token_refresh")
        self.logout_url = reverse("users:auth_logout")

        self.cookie_name = getattr(settings, "JWT_AUTH_COOKIE", "refresh_token")
        self.cookie_path = getattr(settings, "JWT_AUTH_COOKIE_PATH", "/")

        self.user_data = {
            "email": "integration_user@example.com",
            "password": "StrongPassword123!",
            "display_name": "Integration User",
        }

    def _set_refresh_cookie(self, token_value: str):
        self.client.cookies[self.cookie_name] = token_value
        self.client.cookies[self.cookie_name]["path"] = self.cookie_path

    def test_full_auth_lifecycle_flow(self):
        register_resp = self.client.post(
            self.register_url,
            data=self.user_data,
            format="json",
        )
        self.assertEqual(register_resp.status_code, status.HTTP_201_CREATED)

        login_resp = self.client.post(
            self.login_url,
            data={
                "email": self.user_data["email"],
                "password": self.user_data["password"],
            },
            format="json",
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        first_access = login_resp.data["access"]

        self.assertIn(self.cookie_name, login_resp.cookies)
        first_refresh = login_resp.cookies[self.cookie_name].value

        me_resp_1 = self.client.get(
            self.me_url,
            HTTP_AUTHORIZATION=f"Bearer {first_access}",
        )
        self.assertEqual(me_resp_1.status_code, status.HTTP_200_OK)

        refresh_resp = self.client.post(self.refresh_url)
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        second_access = refresh_resp.data["access"]
        self.assertNotEqual(first_access, second_access)

        me_resp_2 = self.client.get(
            self.me_url,
            HTTP_AUTHORIZATION=f"Bearer {second_access}",
        )
        self.assertEqual(me_resp_2.status_code, status.HTTP_200_OK)

        logout_resp = self.client.post(self.logout_url)
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(logout_resp.cookies[self.cookie_name].value, "")

        self._set_refresh_cookie(first_refresh)
        failed_refresh = self.client.post(self.refresh_url)
        self.assertIn(
            failed_refresh.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED],
        )

    def test_expired_access_token(self):
        user = User.objects.create_user(**self.user_data)
        token = AccessToken.for_user(user)
        token.set_exp(lifetime=-timedelta(seconds=1))

        response = self.client.get(
            self.me_url,
            HTTP_AUTHORIZATION=f"Bearer {token!s}",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_access_token(self):
        response = self.client.get(
            self.me_url,
            HTTP_AUTHORIZATION="Bearer invalid.token.value",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_refresh_token(self):
        user = User.objects.create_user(**self.user_data)
        raw_refresh, session = UserService.create_refresh_token_for_user(user)

        session.expires_at = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=["expires_at"])

        self._set_refresh_cookie(raw_refresh)
        response = self.client.post(self.refresh_url)

        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED],
        )

    def test_revoked_refresh_token(self):
        user = User.objects.create_user(**self.user_data)
        raw_refresh, session = UserService.create_refresh_token_for_user(user)

        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at"])

        self._set_refresh_cookie(raw_refresh)
        response = self.client.post(self.refresh_url)

        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED],
        )

    def test_refresh_token_reuse_detection(self):
        user = User.objects.create_user(**self.user_data)
        raw_refresh, _ = UserService.create_refresh_token_for_user(user)

        self._set_refresh_cookie(raw_refresh)
        rotate_resp = self.client.post(self.refresh_url)
        self.assertEqual(rotate_resp.status_code, status.HTTP_200_OK)

        self._set_refresh_cookie(raw_refresh)
        reuse_resp = self.client.post(self.refresh_url)

        self.assertIn(
            reuse_resp.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED],
        )

    def test_refresh_token_is_never_stored_in_plaintext(self):
        user = User.objects.create_user(**self.user_data)
        raw_refresh, session = UserService.create_refresh_token_for_user(user)

        self.assertIsNotNone(session.token_hash)
        self.assertNotIn(raw_refresh, session.token_hash)

        for s in UserRefreshToken.objects.all():
            self.assertNotEqual(getattr(s, "token_hash", None), raw_refresh)
            self.assertFalse(raw_refresh in str(s.__dict__))
