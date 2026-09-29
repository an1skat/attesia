from django.db.models import QuerySet

from app.modules.events.models import (
    Event,
    EventAchievement,
    EventParticipant,
    ParticipantAchievement,
)


def get_all_events() -> QuerySet[Event]:
    return Event.objects.select_related("organization").all()


def get_events_by_organization(organization_id: int) -> QuerySet[Event]:
    return Event.objects.filter(organization_id=organization_id).all()


def get_events_by_id(event_id: int) -> Event:
    return Event.objects.get(id=event_id)


def get_event_participants(event_id: int) -> QuerySet[EventParticipant]:
    return (
        EventParticipant.objects.filter(event_id=event_id).select_related("user").all()
    )


def get_event_achievements(event_id: int) -> QuerySet[EventAchievement]:
    return EventAchievement.objects.filter(event_id=event_id).all()


def get_participant_achievement_from_event(
    *,
    event: Event,
    participant_id: int | str | None = None,
) -> QuerySet[ParticipantAchievement]:
    queryset = ParticipantAchievement.objects.filter(
        participant__event=event,
    ).select_related("participant", "achievement")

    if participant_id:
        queryset = queryset.filter(participant_id=participant_id)

    return queryset
