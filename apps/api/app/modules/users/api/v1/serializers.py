from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from app.core.auth.tokens import generate_auth_tokens
from app.modules.users.models import UserRefreshToken

User = get_user_model()


class UserRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "display_name", "email", "password")
        extra_kwargs = {
            "password": {"write_only": True},
            "style": {"input_type": "password"},
            "email": {"required": True},
        }

    # def validate_email(self, value):
    #     if User.objects.filter(email=value).exists():
    #         raise serializers.ValidationError("Email already exists")
    #     return value

    def validate(self, data):
        user = User(email=data.get("email"), display_name=data.get("display_name"))
        password = data.get("password")

        try:
            validate_password(password=password, user=user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return data

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data.get("email"),
            display_name=validated_data.get("display_name"),
            password=validated_data.get("password"),
        )


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(
                email=email,
                password=password,
            )
            if not user:
                raise serializers.ValidationError("Invalid credentials")

        else:
            raise serializers.ValidationError("Must include 'email' and 'password'")
        return generate_auth_tokens(user)


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        refresh_token_str = attrs.get("refresh")
        try:
            refresh_obj = UserRefreshToken.objects.get(token=refresh_token_str)
        except ObjectDoesNotExist:
            raise serializers.ValidationError("Refresh token does not exist")

        if refresh_obj.is_expired:
            refresh_obj.delete()
            raise serializers.ValidationError("Refresh token expired")

        user = refresh_obj.user
        refresh_obj.delete()

        return generate_auth_tokens(user)
