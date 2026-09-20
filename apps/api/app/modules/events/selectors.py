from django.db.models import QuerySet

from app.modules.events.models import Event


def get_all_events() -> QuerySet[Event]:
    return Event.objects.select_related("organization").all()


def get_events_by_organization(organization_id: int) -> QuerySet[Event]:
    return Event.objects.filter(organization_id=organization_id).all()


def get_events_by_id(event_id: int) -> Event:
    return Event.objects.get(id=event_id)
