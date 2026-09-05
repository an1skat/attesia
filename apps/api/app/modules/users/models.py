import uuid
from datetime import timedelta
from typing import ClassVar

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractUser):
    username = None
    date_joined = None
    first_name = None
    last_name = None

    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=150)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["display_name"]

    def get_full_name(self) -> str:
        return self.display_name

    def get_short_name(self) -> str:
        return self.display_name

    objects = UserManager()


class UserRefreshToken(models.Model):
    objects: ClassVar[models.Manager] = models.Manager()

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="refresh_tokens",
    )
    token_hash = models.CharField(max_length=255, unique=True, db_index=True)

    family_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and timezone.now() < self.expires_at

    def revoke(self):
        if not self.revoked_at:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

    @classmethod
    def revoke_family(cls, family_id: uuid.UUID):
        cls.objects.filter(family_id=family_id, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )

    def save(self, *args, **kwargs):
        if not self.expires_at:
            days = getattr(settings, "REFRESH_TOKEN_LIFETIME_DAYS", 30)
            self.expires_at = timezone.now() + timedelta(days=days)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Refresh for {self.user.email} (expired: {self.is_expired})"
