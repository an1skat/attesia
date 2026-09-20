from typing import ClassVar

from rest_framework import serializers

from app.modules.events.models import Event, EventStatus


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
