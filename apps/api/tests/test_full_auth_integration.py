from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AuthFullIntegrationTestCase(APITestCase):
    def setUp(self):
        self.register_url = reverse("users:user_register")
        self.login_url = reverse("users:token_obtain")
        self.me_url = reverse("users:user_profile")
        self.refresh_url = reverse("users:token_refresh")
        self.logout_url = reverse("users:auth_logout")

        self.cookie_name = getattr(settings, "JWT_AUTH_REFRESH_COOKIE", "refresh_token")
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

        self.assertIn(self.cookie_name, refresh_resp.cookies)
        second_refresh = refresh_resp.cookies[self.cookie_name].value
        self.assertNotEqual(first_refresh, second_refresh)

        me_resp_2 = self.client.get(
            self.me_url,
            HTTP_AUTHORIZATION=f"Bearer {second_access}",
        )
        self.assertEqual(me_resp_2.status_code, status.HTTP_200_OK)

        logout_resp = self.client.post(self.logout_url)
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)

        self.assertIn(self.cookie_name, logout_resp.cookies)
        self.assertEqual(logout_resp.cookies[self.cookie_name].value, "")

        self._set_refresh_cookie(second_refresh)

        failed_refresh = self.client.post(self.refresh_url)

        self.assertIn(
            failed_refresh.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED],
        )
