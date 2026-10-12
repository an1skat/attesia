from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import get_object_or_404

from app.modules.events.finalization import (
    build_finalization_payload,
    hash_finalization_payload,
)
from app.modules.events.models import (
    Event,
    EventAchievement,
    EventFinalization,
    EventParticipant,
    EventParticipantStatus,
    EventStatus,
    ParticipantAchievement,
)
from app.modules.organizations.models import Organization, OrganizationMembership


class EventService:
    @staticmethod
    @transaction.atomic
    def create_event(*, organization: Organization, validated_data: dict) -> Event:
        _reject_finished_status(validated_data)
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
        event = _lock_editable_event(event)
        _reject_finished_status(validated_data)
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
        event = _lock_editable_event(event)
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
        event = _lock_editable_event(event)
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

        event = _lock_editable_event(event)
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
        event = _lock_editable_event(event)
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
        event = _lock_editable_event(event)
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
        event = _lock_editable_event(event)
        participant_achievement = get_object_or_404(
            ParticipantAchievement,
            id=participant_achievement_id,
            achievement__event=event,
        )

        participant_achievement.delete()

    @staticmethod
    @transaction.atomic
    def finalize_event(*, event: Event, finalized_by) -> EventFinalization:
        event = Event.objects.select_for_update().get(pk=event.pk)
        if event.finalizations.exists():
            raise DRFValidationError(
                {"detail": "This event has already been finalized."}
            )
        if event.status != EventStatus.IN_PROGRESS:
            raise DRFValidationError(
                {"status": "Only an in-progress event can be finalized."}
            )
        if not OrganizationMembership.objects.filter(
            organization_id=event.organization_id,
            user=finalized_by,
            role__in=[
                OrganizationMembership.Role.OWNER,
                OrganizationMembership.Role.ADMIN,
            ],
        ).exists():
            raise DRFValidationError(
                {"detail": "Only an organization owner or admin can finalize an event."}
            )
        event.status = EventStatus.FINISHED
        event.save(update_fields=["status", "updated_at"])
        payload = build_finalization_payload(event)
        return EventFinalization.objects.create(
            event=event,
            version=1,
            schema_version=payload["schema_version"],
            payload=payload,
            payload_hash=hash_finalization_payload(payload),
            finalized_by=finalized_by,
        )


def _lock_editable_event(event):
    event = Event.objects.select_for_update().get(pk=event.pk)
    if event.status == EventStatus.FINISHED or event.finalizations.exists():
        raise DRFValidationError(
            {"detail": "Finished events are sealed against editing."}
        )
    return event


def _reject_finished_status(data):
    if data.get("status") == EventStatus.FINISHED:
        raise DRFValidationError(
            {"status": "Use the dedicated event finalization operation."}
        )
