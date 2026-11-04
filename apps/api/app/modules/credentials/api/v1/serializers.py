from rest_framework import serializers

from app.modules.credentials.models import Credential, CredentialAchievement
from app.modules.events.models import EventFinalization


class CredentialAchievementSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CredentialAchievement
        fields = ("title", "description", "kind", "rank")
        read_only_fields = fields


class CredentialFinalizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventFinalization
        fields = ("version", "schema_version", "finalized_at")
        read_only_fields = fields


class CredentialSerializer(serializers.ModelSerializer):
    """Historical credential representation built only from stored snapshots."""

    achievements = CredentialAchievementSnapshotSerializer(
        source="achievement_snapshots", many=True, read_only=True
    )
    finalization = CredentialFinalizationSerializer(read_only=True)

    class Meta:
        model = Credential
        fields = (
            "public_id",
            "organization",
            "organization_title",
            "event",
            "event_title",
            "participant",
            "recipient_user",
            "recipient_name",
            "achievements",
            "finalization",
            "issued_by",
            "issued_at",
            "revoked_at",
            "revoked_by",
            "revocation_reason",
        )
        read_only_fields = fields


class StrictInputSerializer(serializers.Serializer):
    """Reject unknown input keys so server-derived fields cannot be supplied."""

    def to_internal_value(self, data):
        if hasattr(data, "keys"):
            unknown = sorted(set(data.keys()) - set(self.fields))
            if unknown:
                raise serializers.ValidationError(
                    {key: "This field is not accepted." for key in unknown}
                )
        return super().to_internal_value(data)


class CredentialIssueSerializer(StrictInputSerializer):
    participant_id = serializers.IntegerField()
    participant_achievement_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False
    )


class CredentialRevokeSerializer(StrictInputSerializer):
    reason = serializers.CharField(allow_blank=True, trim_whitespace=False)


class CredentialFilterSerializer(serializers.Serializer):
    participant_id = serializers.IntegerField(required=False)
