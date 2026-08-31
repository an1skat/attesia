from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


class UserService:
    @staticmethod
    @transaction.atomic
    def register_user(validate_data: dict) -> User:
        user = User.objects.create_user(
            email=validate_data["email"],
            display_name=validate_data["display_name"],
            password=validate_data["password"],
        )
        return user
