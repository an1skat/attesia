from rest_framework import permissions
from rest_framework.permissions import BasePermission

from app.modules.organizations.models import Organization, OrganizationMembership


class IsOrganizationAdminOrOwner(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        organization = (
            obj if isinstance(obj, Organization) else getattr(obj, "organization", None)
        )
        if not organization:
            return False

        membership = OrganizationMembership.objects.filter(
            organization=organization,
            user=request.user,
        ).first()

        if not membership:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return membership.role in [
            OrganizationMembership.Role.ADMIN,
            OrganizationMembership.Role.OWNER,
        ]
