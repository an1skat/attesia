from typing import ClassVar

from rest_framework import serializers

from app.modules.events.models import Event


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
