# Create your models here.
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint
from django.utils.translation import gettext_lazy as _

from app.modules.organizations.models import Organization


class EventStatus(models.TextChoices):
    PLANNED = "planned", _("Planned")
    REGISTRATION_OPEN = "registration_open", _("Register open")
    IN_PROGRESS = "in_progress", _("In progress")
    FINISHED = "finished", _("Finished")
    CANCELED = "canceled", _("Canceled")


class EventParticipantStatus(models.TextChoices):
    MANUAL = "manual", _("Manual")
    REGISTER = "register", _("Register")
    IMPORT = "import", _("Import")


class EventAchievementKind(models.TextChoices):
    PLACE = "place", _("Place")
    NOMINATION = "nomination", _("Nomination")
    PARTICIPANT = "participant", _("Participant")


class Event(models.Model):
    Status = EventStatus

    objects: models.Manager = models.Manager()

    title = models.CharField(max_length=150, db_index=True)
    description = models.TextField(max_length=1500, blank=True)

    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        db_index=True,
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_("Provide the address, venue name, or link to the live stream"),
    )

    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_events",
    )

    organization_title = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
        help_text=_("Historical name of the organization"),
    )

    def save(self, *args, **kwargs):
        if not self.pk and self.organization:
            self.organization_title = self.organization.name
        super().save(*args, **kwargs)

    @property
    def organization_display_name(self):
        return self.organization_title or _("Unknown Organization")

    class Meta:
        verbose_name = _("Event")
        verbose_name_plural = _("Events")
        ordering: ClassVar[list] = ["-starts_at"]
        constraints: ClassVar[list] = [
            CheckConstraint(
                condition=Q(starts_at__isnull=True)
                | Q(ends_at__isnull=True)
                | Q(ends_at__gte=F("starts_at")),
                name="event_ends_at_gte_starts_at",
            ),
            CheckConstraint(
                condition=Q(status__in=EventStatus.values),
                name="event_status_valid_choice",
            ),
            CheckConstraint(
                condition=Q(organization__isnull=False) | ~Q(organization_title=""),
                name="event_require_title_when_no_organization",
            ),
        ]

    def __str__(self):
        return self.title or f"Untitled - #{self.pk}"

    def clean(self):
        super().clean()
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            raise ValidationError(
                {
                    "ends_at": _("The end date cannot be earlier than the start date"),
                }
            )
        if not self.organization and not self.organization_title:
            raise ValidationError(
                {
                    "organization_title": _(
                        "Organization title is required when no organization is attached."
                    ),
                }
            )


class EventParticipant(models.Model):
    Status = EventParticipantStatus

    objects: models.Manager = models.Manager()

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="participants",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_participants",
    )

    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)

    source = models.CharField(
        max_length=20,
        choices=EventParticipantStatus.choices,
        default=EventParticipantStatus.MANUAL,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Participant")
        verbose_name_plural = _("Participants")
        ordering: ClassVar[list] = ["-created_at"]
        constraints: ClassVar[list] = [
            UniqueConstraint(
                fields=["event", "email"],
                name="unique_participant_email_per_event",
            ),
            UniqueConstraint(
                fields=["event", "user"],
                condition=Q(user__isnull=False),
                name="unique_participant_user_per_event",
            ),
        ]

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.lower().strip()

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.event.title}"


class EventAchievement(models.Model):
    Status = EventAchievementKind

    objects: models.Manager = models.Manager()

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="event_achievements",
    )
    title = models.CharField(max_length=50)
    kind = models.CharField(
        max_length=15,
        choices=EventAchievementKind.choices,
        default=EventAchievementKind.PARTICIPANT,
        db_index=True,
    )
    rank = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Numerical rank for place achievements (e.g. 1 for 1st place)"),
    )
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Event Achievement")
        verbose_name_plural = _("Event Achievements")
        ordering: ClassVar[list] = ["kind", "rank", "title"]
        constraints: ClassVar[list] = [
            CheckConstraint(
                condition=Q(kind__in=EventAchievementKind.values),
                name="event_achievement_kind_valid_choice",
            ),
            CheckConstraint(
                condition=Q(rank__gt=0) | Q(rank__isnull=True),
                name="event_achievement_rank_positive",
            ),
            models.UniqueConstraint(
                fields=["event", "rank"],
                condition=Q(kind=EventAchievementKind.PLACE),
                name="unique_place_rank_per_event",
            ),
        ]

    def clean(self):
        super().clean()
        if self.kind == EventAchievementKind.PLACE and self.rank is None:
            raise ValidationError(
                {"rank": _("Rank is required for 'place' achievements.")}
            )

    def __str__(self):
        if self.rank:
            return f"{self.title} (#{self.rank}) - {self.event.title}"
        return f"{self.title} - {self.event.title}"
