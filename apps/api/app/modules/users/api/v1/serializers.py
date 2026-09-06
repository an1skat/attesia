from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

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

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate(self, data):
        user = User(email=data.get("email"), display_name=data.get("display_name"))
        password = data.get("password")

        try:
            validate_password(password=password, user=user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return data


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(email=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials")

        attrs["user"] = user
        return attrs


class RefreshTokenSerializer(serializers.Serializer):
    def validate(self, attrs):
        request = self.context.get("request")
        raw_token = request.COOKIES.get("refresh_token")

        if not raw_token:
            raise serializers.ValidationError("Refresh token cookie is missing")

        attrs["raw_token"] = raw_token
        return attrs
