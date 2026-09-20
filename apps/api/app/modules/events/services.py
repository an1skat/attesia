from django.db import transaction

from app.modules.events.models import Event, EventStatus
from app.modules.organizations.models import Organization


class EventService:
    @staticmethod
    @transaction.atomic
    def create_event(*, organization: Organization, validate_data: dict) -> Event:
        event = Event(
            organization=organization,
            title=validate_data["title"],
            description=validate_data.get("description", ""),
            status=validate_data.get("status", EventStatus.PLANNED),
            location=validate_data.get("location", ""),
            starts_at=validate_data.get("starts_at"),
            ends_at=validate_data.get("ends_at"),
        )
        event.full_clean()
        event.save()
        return event

    @staticmethod
    @transaction.atomic
    def update_event(*, event: Event, validate_data: dict) -> Event:
        for field, value in validate_data.items():
            setattr(event, field, value)

        event.full_clean()
        event.save()
        return event
