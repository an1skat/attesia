from rest_framework import serializers

from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.organizations.services import create_organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("id", "name", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def create(self, validated_data):
        return create_organization(
            owner=self.context["request"].user, name=validated_data["name"]
        )


class PublicUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    display_name = serializers.CharField(read_only=True)


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = ("id", "user", "role", "created_at")
        read_only_fields = fields


class OrganizationMembershipCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    role = serializers.ChoiceField(
        choices=(OrganizationMembership.Role.ADMIN, OrganizationMembership.Role.MEMBER)
    )
