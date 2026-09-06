from rest_framework import serializers

from app.modules.organizations.models import Organization
from app.modules.organizations.services import create_organization


class OrganizationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("id", "name", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def create(self, validated_data):
        return create_organization(
            owner=self.context["request"].user, name=validated_data["name"]
        )
