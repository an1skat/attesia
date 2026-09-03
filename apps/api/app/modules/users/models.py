import secrets
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
        related_name="refresh_token",
    )
    token = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        if not self.expires_at:
            days = getattr(settings, "REFRESH_TOKEN_LIFETIME_DAYS", 30)
            self.expires_at = timezone.now() + timezone.timedelta(days=days)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Refresh for {self.user.email} (expired: {self.is_expired})"
