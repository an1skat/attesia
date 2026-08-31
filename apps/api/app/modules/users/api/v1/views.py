from typing import ClassVar

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from app.modules.users.services import UserService

from .serializers import UserRegisterSerializer

User = get_user_model()


class RegisterView(APIView):
    permissions_classes: ClassVar[list] = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = UserService.register_user(serializer.validated_data)
        response_serializer = UserRegisterSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
