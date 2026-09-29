from typing import ClassVar

from rest_framework import serializers

from app.modules.events.models import (
    Event,
    EventAchievement,
    EventAchievementKind,
    EventParticipant,
    EventStatus,
    ParticipantAchievement,
)


class EventSerializer(serializers.ModelSerializer):
    organization_display_name = serializers.ReadOnlyField()

    class Meta:
        model = Event
        fields = (
            "id",
            "title",
            "description",
            "status",
            "location",
            "starts_at",
            "ends_at",
            "organization",
            "organization_title",
            "organization_display_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "organization_title",
            "created_at",
            "updated_at",
        )


class EventCreateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=EventStatus.choices, required=True)

    class Meta:
        model = Event
        fields = (
            "title",
            "description",
            "status",
            "location",
            "starts_at",
            "ends_at",
        )

    def validate(self, attrs):
        starts_at = attrs.get("starts_at")
        ends_at = attrs.get("ends_at")

        if starts_at and ends_at and ends_at < starts_at:
            raise serializers.ValidationError(
                {"ends_at": "Ends at date cannot be earlier than starts at date."},
            )
        return attrs


class EventUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = (
            "title",
            "description",
            "status",
            "location",
            "starts_at",
            "ends_at",
        )
        extra_kwargs: ClassVar[dict] = {field: {"required": False} for field in fields}


class EventParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventParticipant
        fields = (
            "id",
            "name",
            "email",
            "source",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "source", "created_at", "updated_at")


class EventParticipantCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventParticipant
        fields = (
            "name",
            "email",
            "user",
        )


class EventAchievementSerializer(serializers.ModelSerializer):
    kind = serializers.ChoiceField(choices=EventAchievementKind.choices)

    class Meta:
        model = EventAchievement
        fields = (
            "id",
            "title",
            "kind",
            "rank",
            "description",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )


class EventAchievementCreateSerializer(serializers.ModelSerializer):
    kind = serializers.ChoiceField(choices=EventAchievementKind.choices)

    class Meta:
        model = EventAchievement
        fields = (
            "title",
            "kind",
            "rank",
            "description",
        )

    def validate(self, attrs):
        kind = attrs.get("kind")
        rank = attrs.get("rank")

        if kind == EventAchievementKind.PLACE:
            if rank is None or rank <= 0:
                raise serializers.ValidationError(
                    {"rank": "Rank is required when kind is 'place'."}
                )
        else:
            if rank is not None:
                raise serializers.ValidationError(
                    {"rank": "Rank must be empty (null) for non-place achievements."}
                )

        return attrs


class ParticipantAchievementSerializer(serializers.ModelSerializer):
    participant_name = serializers.CharField(source="participant.name", read_only=True)
    participant_email = serializers.CharField(
        source="participant.email", read_only=True
    )
    achievement_title = serializers.CharField(
        source="achievement.title", read_only=True
    )
    achievement_kind = serializers.CharField(source="achievement.kind", read_only=True)
    achievement_rank = serializers.IntegerField(
        source="achievement.rank", read_only=True
    )

    class Meta:
        model = ParticipantAchievement
        fields = (
            "id",
            "participant",
            "participant_name",
            "participant_email",
            "achievement",
            "achievement_title",
            "achievement_kind",
            "achievement_rank",
            "awarded_at",
        )
        read_only_fields = ("id", "awarded_at")


class ParticipantAchievementFilterSerializer(serializers.Serializer):
    participant_id = serializers.IntegerField(required=False)


class ParticipantAchievementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParticipantAchievement
        fields = (
            "participant",
            "achievement",
        )

    def validate(self, attrs):
        participant = attrs.get("participant")
        achievement = attrs.get("achievement")

        if participant and achievement and participant.event_id != achievement.event_id:
            raise serializers.ValidationError(
                {
                    "achievement": (
                        "The achievement does not belong to the same event as the participant."
                    )
                }
            )

        if ParticipantAchievement.objects.filter(
            participant=participant,
            achievement=achievement,
        ).exists():
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "This achievement has already been awarded to this participant."
                    ]
                }
            )

        return attrs
