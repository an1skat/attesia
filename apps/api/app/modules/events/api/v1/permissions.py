from rest_framework.permissions import BasePermission

from app.modules.organizations.models import Organization, OrganizationMembership


class IsOrganizationAdminOrOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        organization = obj if isinstance(obj, Organization) else obj.organization
        return OrganizationMembership.objects.filter(
            organization=organization,
            user=request.user,
            role__in=[
                OrganizationMembership.Role.ADMIN,
                OrganizationMembership.Role.OWNER,
            ],
        ).exists()
