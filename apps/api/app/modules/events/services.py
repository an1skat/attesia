from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import get_object_or_404

from app.modules.events.models import (
    Event,
    EventAchievement,
    EventParticipant,
    EventParticipantStatus,
    ParticipantAchievement,
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

    @staticmethod
    @transaction.atomic
    def add_achievement(
        *,
        event: Event,
        validated_data: dict,
    ) -> EventAchievement:

        achievement = EventAchievement(
            event=event,
            title=validated_data["title"],
            kind=validated_data["kind"],
            rank=validated_data.get("rank"),
            description=validated_data.get("description", ""),
        )
        try:
            achievement.full_clean()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message_dict)
        achievement.save()
        return achievement

    @staticmethod
    @transaction.atomic
    def remove_achievement(
        *,
        event: Event,
        achievement_id: int,
    ) -> None:
        try:
            achievement = get_object_or_404(
                EventAchievement,
                id=achievement_id,
                event=event,
            )
            achievement.delete()
        except ObjectDoesNotExist:
            raise DRFValidationError({"detail": "Achievement not found in this event."})

    @staticmethod
    @transaction.atomic
    def award_achievement_to_participant(
        *,
        event: Event,
        validated_data: dict,
    ) -> ParticipantAchievement:
        participant = validated_data["participant"]
        achievement = validated_data["achievement"]

        if participant.event_id != event.id or achievement.event_id != event.id:
            raise DRFValidationError(
                {
                    "detail": "Participant and achievement must belong to this specific event."
                }
            )

        participant_achievement = ParticipantAchievement(
            participant=participant,
            achievement=achievement,
        )

        try:
            participant_achievement.full_clean()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message_dict)
        participant_achievement.save()
        return participant_achievement

    @staticmethod
    @transaction.atomic
    def revoke_achievement_from_participant(
        *,
        event: Event,
        participant_achievement_id: int,
    ) -> None:
        participant_achievement = get_object_or_404(
            ParticipantAchievement,
            id=participant_achievement_id,
            achievement__event=event,
        )

        participant_achievement.delete()
