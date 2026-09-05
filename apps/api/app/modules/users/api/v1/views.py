from typing import ClassVar

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from app.modules.users.services import UserService

from .serializers import (
    RefreshTokenSerializer,
    UserLoginSerializer,
    UserRegisterSerializer,
)

User = get_user_model()


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    days = getattr(settings, "REFRESH_TOKEN_LIFETIME_DAYS", 30)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        max_age=3600 * 24 * days,
        path="/",
    )


class RegisterView(APIView):
    permission_classes: ClassVar[list] = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = UserService.register_user(serializer.validated_data)
        response_serializer = UserRegisterSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes: ClassVar[list] = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        raw_refresh, _ = UserService.create_refresh_token_for_user(user=user)
        access_token = str(AccessToken.for_user(user))

        response = Response(
            {"access": access_token},
            status=status.HTTP_200_OK,
        )
        set_refresh_cookie(response, raw_refresh)
        return response


class CustomRefreshToken(APIView):
    permission_classes: ClassVar[list] = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RefreshTokenSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        raw_token = serializer.validated_data["raw_token"]
        access_token, new_refresh_token = UserService.rotate_refresh_token(raw_token)

        response = Response({"access": access_token}, status=status.HTTP_200_OK)
        set_refresh_cookie(response, new_refresh_token)
        return response
