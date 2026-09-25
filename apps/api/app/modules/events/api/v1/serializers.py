from typing import ClassVar

from rest_framework import serializers

from app.modules.events.models import (
    Event,
    EventParticipant,
    EventStatus,
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
            "event",
            "user",
            "name",
            "email",
            "source",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "event", "created_at", "updated_at")


class EventParticipantCreateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, max_length=255)
    email = serializers.EmailField(required=True)

    class Meta:
        model = EventParticipant
        fields = ("user", "name", "email")

    def validate(self, attrs):
        user = attrs.get("user")
        name = attrs.get("name")
        email = attrs.get("email")

        if not user and not (name and email):
            raise serializers.ValidationError(
                "Either 'user' or both 'name' and 'email' must be provided."
            )
        return attrs
