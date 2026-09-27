from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import get_object_or_404

from app.modules.events.models import (
    Event,
    EventParticipant,
    EventParticipantStatus,
)
from app.modules.organizations.models import Organization


class EventService:
    @staticmethod
    @transaction.atomic
    def create_event(*, organization: Organization, validated_data: dict) -> Event:
        event = Event(
            organization=organization,
            title=validated_data["title"],
            description=validated_data.get("description", ""),
            status=validated_data["status"],
            location=validated_data.get("location", ""),
            starts_at=validated_data.get("starts_at"),
            ends_at=validated_data.get("ends_at"),
        )
        try:
            event.full_clean()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message_dict)
        event.save()
        return event

    @staticmethod
    @transaction.atomic
    def update_event(*, event: Event, validated_data: dict) -> Event:
        for field, value in validated_data.items():
            setattr(event, field, value)

        try:
            event.full_clean()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message_dict)
        event.save()
        return event

    @staticmethod
    @transaction.atomic
    def add_participant(
        *,
        event: Event,
        validated_data: dict,
        source: str = EventParticipantStatus.MANUAL,
    ) -> EventParticipant:
        email = validated_data["email"].lower().strip()

        if EventParticipant.objects.filter(event=event, email=email).exists():
            raise DRFValidationError(
                {"email": "Participant with this email already exists in this event."}
            )

        user = validated_data.get("user")
        if user and EventParticipant.objects.filter(event=event, user=user).exists():
            raise DRFValidationError(
                {"user": "Participant with this user already exists in this event."}
            )

        participant = EventParticipant(
            event=event,
            user=user,
            name=validated_data["name"],
            email=email,
            source=source,
        )
        try:
            participant.full_clean()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message_dict)

        participant.save()
        return participant

    @staticmethod
    @transaction.atomic
    def remove_participant(
        *,
        event: Event,
        participant_id: int,
    ) -> None:
        try:
            participant = get_object_or_404(
                EventParticipant,
                id=participant_id,
                event=event,
            )
            participant.delete()
        except ObjectDoesNotExist:
            raise DRFValidationError({"detail": "Participant not found in this event."})
