from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from app.modules.events.models import Event, EventParticipant, ParticipantSource
from app.modules.organizations.models import Organization


class EventService:
    @staticmethod
    @transaction.atomic
    def create_event(*, organization: Organization, validate_data: dict) -> Event:
        event = Event(
            organization=organization,
            title=validate_data["title"],
            description=validate_data.get("description", ""),
            status=validate_data["status"],
            location=validate_data.get("location", ""),
            starts_at=validate_data.get("starts_at"),
            ends_at=validate_data.get("ends_at"),
        )
        try:
            event.full_clean()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message_dict)
        event.save()
        return event

    @staticmethod
    @transaction.atomic
    def update_event(*, event: Event, validate_data: dict) -> Event:
        for field, value in validate_data.items():
            setattr(event, field, value)

        try:
            event.full_clean()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message_dict)
        event.save()
        return event

    @staticmethod
    @transaction.atomic
    def add_participant(*, event: Event, validate_data: dict) -> Event:
        participant = EventParticipant(
            event=event,
            user=validate_data.get("user"),
            name=validate_data.get("name"),
            email=validate_data.get("email"),
            source=validate_data.get("source", ParticipantSource.MANUAL),
        )
        try:
            participant.full_clean()
        except DjangoValidationError as e:
            raise DRFValidationError(
                e.message_dict if hasattr(e, "message_dict") else e.messages
            )
        participant.save()
        return participant

    @staticmethod
    @transaction.atomic
    def remove_participant(*, participant: EventParticipant) -> None:
        participant.delete()
