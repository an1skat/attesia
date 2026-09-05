import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions
from rest_framework_simplejwt.tokens import AccessToken

from app.modules.users.models import UserRefreshToken

User = get_user_model()


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


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

    @classmethod
    def create_refresh_token_for_user(
        cls, user, family_id: uuid.UUID | None = None
    ) -> tuple[str, UserRefreshToken]:
        raw_token = secrets.token_urlsafe(32)
        hashed = hash_token(raw_token)

        if family_id is None:
            family_id = uuid.uuid4()

        days = getattr(settings, "REFRESH_TOKEN_LIFETIME_DAYS", 30)
        expires_at = timezone.now() + timedelta(days=days)
        refresh_obj = UserRefreshToken.objects.create(
            user=user,
            token_hash=hashed,
            family_id=family_id,
            expires_at=expires_at,
        )
        return raw_token, refresh_obj

    @classmethod
    def rotate_refresh_token(cls, raw_token: str) -> tuple[str, str]:
        if not raw_token:
            raise exceptions.ValidationError(
                {"refresh": "Refresh token cookie is missing"}
            )

        incoming_hash = hash_token(raw_token)
        with transaction.atomic():
            token_obj = (
                UserRefreshToken.objects.select_for_update()
                .filter(token_hash=incoming_hash)
                .first()
            )

            if not token_obj:
                raise exceptions.ValidationError({"refresh": "Invalid refresh token"})

            if token_obj.revoked_at is not None:
                UserRefreshToken.revoke_family(token_obj.family_id)
                is_compromised = True
            else:
                is_compromised = False

            if not is_compromised and token_obj.expires_at < timezone.now():
                token_obj.revoke()
                is_expired = True
            else:
                is_expired = False

            if not is_compromised and not is_expired:
                token_obj.revoke()
                new_raw_refresh, _ = cls.create_refresh_token_for_user(
                    user=token_obj.user,
                    family_id=token_obj.family_id,
                )
                access_token = str(AccessToken.for_user(token_obj.user))

        if is_compromised:
            raise exceptions.ValidationError(
                {"refresh": "Token has been revoked. Family compromised."}
            )

        if is_expired:
            raise exceptions.ValidationError({"refresh": "Token has expired"})

        return access_token, new_raw_refresh
