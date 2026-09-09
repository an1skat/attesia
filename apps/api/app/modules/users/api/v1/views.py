from typing import ClassVar

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from app.modules.users.services import UserService

from .serializers import (
    RefreshTokenSerializer,
    UserLoginSerializer,
    UserMeSerializer,
    UserRegisterSerializer,
)

User = get_user_model()


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    days = getattr(settings, "REFRESH_TOKEN_LIFETIME_DAYS", 30)
    response.set_cookie(
        key=getattr(settings, "JWT_AUTH_REFRESH_COOKIE", "refresh_token"),
        value=refresh_token,
        httponly=getattr(settings, "JWT_AUTH_COOKIE_HTTPONLY", True),
        secure=not settings.DEBUG,
        samesite=getattr(settings, "JWT_AUTH_COOKIE_SAMESITE", "Lax"),
        max_age=3600 * 24 * days,
        path=getattr(settings, "JWT_AUTH_COOKIE_PATH", "/"),
    )


class UserProfileView(APIView):
    permission_classes: ClassVar[list] = [IsAuthenticated]

    def get(self, request):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserMeSerializer(
            instance=request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        update_user = UserService.update_user_profile(
            user=request.user,
            data=serializer.validated_data,
        )
        return Response(
            UserMeSerializer(update_user).data,
            status=status.HTTP_200_OK,
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


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        cookie_name = getattr(settings, "JWT_AUTH_REFRESH_COOKIE", "refresh_token")
        raw_refresh_token = request.COOKIES.get(cookie_name)

        UserService.logout_user(raw_refresh_token=raw_refresh_token)
        response = Response(
            {"message": "Successfully logged out"},
            status=status.HTTP_200_OK,
        )

        response.delete_cookie(
            key=cookie_name,
            path=getattr(settings, "JWT_AUTH_COOKIE_PATH", "/"),
            samesite=getattr(settings, "JWT_AUTH_COOKIE_SAMESITE", "Lax"),
        )

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
