# Create your models here.
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from app.modules.organizations.models import Organization


class Event(models.Model):
    class Status(models.TextChoices):
        __empty__ = _("Select the event status")

        PLANNED = "planned", _("Planned")
        REGISTRATION_OPEN = "registration_open", _("Register open")
        IN_PROGRESS = "in_progress", _("In progress")
        FINISHED = "finished", _("Finished")
        CANCELED = "canceled", _("Canceled")

    title = models.CharField(max_length=150, db_index=True)
    description = models.TextField(max_length=1500, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
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

    organizator = models.ForeignKey(
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
        if self.organizator:
            self.organization_title = self.organizator.name
        super().save(*args, **kwargs)

    @property
    def organization_display_name(self):
        if self.organizator:
            return self.organizator.name
        return self.organization_title or _("Unknown Organization")

    class Meta:
        verbose_name = _("Event")
        verbose_name_plural = _("Events")
        ordering: ClassVar[list] = ["-starts_at"]

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
