from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


class JWTAuthenticationTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="auth_test@example.com",
            password="StrongPassword123!",
            display_name="Auth Test",
        )
        self.protected_url = reverse("users:user_profile")

    def test_successful_authentication(self):
        token = str(AccessToken.for_user(self.user))
        response = self.client.get(
            self.protected_url,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)

    def test_missing_authorization_header(self):
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_header_format(self):
        token = str(AccessToken.for_user(self.user))
        response = self.client.get(
            self.protected_url,
            HTTP_AUTHORIZATION=f"Token {token}",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_jwt_token(self):
        response = self.client.get(
            self.protected_url,
            HTTP_AUTHORIZATION="Bearer invalid.jwt.string",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_existent_user_in_sub(self):
        token = AccessToken.for_user(self.user)
        token["user_id"] = 999999
        token["sub"] = 999999

        response = self.client.get(
            self.protected_url,
            HTTP_AUTHORIZATION=f"Bearer {token!s}",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user(self):
        self.user.is_active = False
        self.user.save()

        token = str(AccessToken.for_user(self.user))
        response = self.client.get(
            self.protected_url,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
