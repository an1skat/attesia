import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone

from app.modules.events.models import (
    Event,
    EventAchievementKind,
    EventFinalization,
    EventParticipant,
    ParticipantAchievement,
)
from app.modules.organizations.models import Organization


class Credential(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credentials",
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credentials",
    )

    participant = models.ForeignKey(
        EventParticipant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credentials",
    )
    finalization = models.ForeignKey(
        EventFinalization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credentials",
    )

    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credentials",
    )

    organization_title = models.CharField(max_length=255)
    event_title = models.CharField(max_length=150)
    recipient_name = models.CharField(max_length=255)

    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="issued_credentials",
    )

    issued_at = models.DateTimeField(default=timezone.now, editable=False)

    revoked_at = models.DateTimeField(null=True, blank=True)

    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_credentials",
    )

    revocation_reason = models.TextField(blank=True)


class CredentialAchievement(models.Model):
    credential = models.ForeignKey(
        Credential,
        on_delete=models.CASCADE,
        related_name="achievement_snapshots",
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    kind = models.CharField(
        max_length=15, choices=EventAchievementKind.choices, null=True, blank=True
    )
    rank = models.PositiveIntegerField(null=True, blank=True)
    participant_achievement = models.ForeignKey(
        ParticipantAchievement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credential_snapshots",
    )

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["credential", "participant_achievement"],
                name="credential_source_achievement_unique",
            ),
        ]
