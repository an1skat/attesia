from rest_framework.permissions import SAFE_METHODS, BasePermission

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


class IsOrganizationAdminOrOwnerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)

        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        organization = obj if isinstance(obj, Organization) else obj.organization
        if not organization:
            return False

        return OrganizationMembership.objects.filter(
            organization=organization,
            user=request.user,
            role__in=[
                OrganizationMembership.Role.ADMIN,
                OrganizationMembership.Role.OWNER,
            ],
        ).exists()
