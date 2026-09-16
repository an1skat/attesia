# Create your models here.
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Event(models.Model):
    class Status(models.TextChoices):
        REGISTER = "RG", _("Register")
        ENDING = "EN", _("Ending")

    title = models.CharField(max_length=128, blank=True, db_index=True)
    description = models.TextField(blank=True)
    organizator = models.CharField(max_length=128, blank=True, db_index=True)

    status = models.BooleanField(
        max_length=2,
        choices=Status.choices,
        default=Status.REGISTER,
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
