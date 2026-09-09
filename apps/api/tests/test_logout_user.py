from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.modules.users.services import UserService

User = get_user_model()


class LogoutTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="logout_test@example.com",
            password="StrongPassword123!",
            display_name="Logout User",
        )
        self.logout_url = reverse("users:auth_logout")
        self.cookie_name = getattr(settings, "JWT_AUTH_COOKIE", "refresh_token")

        self.raw_refresh, self.session = UserService.create_refresh_token_for_user(
            self.user
        )

    def _set_refresh_cookie(self, token_value: str):
        cookie_path = getattr(settings, "JWT_AUTH_COOKIE_PATH", "/")
        self.client.cookies[self.cookie_name] = token_value
        self.client.cookies[self.cookie_name]["path"] = cookie_path

    def test_successful_logout(self):
        self._set_refresh_cookie(self.raw_refresh)

        response = self.client.post(self.logout_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.revoked_at)

        self.assertIn(self.cookie_name, response.cookies)
        self.assertEqual(response.cookies[self.cookie_name].value, "")

    def test_logout_revokes_only_current_session(self):
        raw_refresh_2, session_2 = UserService.create_refresh_token_for_user(self.user)

        self._set_refresh_cookie(self.raw_refresh)
        response = self.client.post(self.logout_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.revoked_at)

        session_2.refresh_from_db()
        self.assertIsNone(session_2.revoked_at)
