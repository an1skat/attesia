from rest_framework.permissions import SAFE_METHODS, BasePermission

from app.modules.organizations.models import Organization, OrganizationMembership


def _get_organization_from_object(obj):
    if isinstance(obj, Organization):
        return obj
    if hasattr(obj, "organization"):
        return obj.organization
    if hasattr(obj, "event") and hasattr(obj.event, "organization"):
        return obj.event.organization
    return None


class IsOrganizationAdminOrOwnerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        organization = _get_organization_from_object(obj)
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


class IsOrganizationMemberOrAdminForWrite(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        organization = _get_organization_from_object(obj)
        if not organization:
            return False

        if request.method in SAFE_METHODS:
            return OrganizationMembership.objects.filter(
                organization=organization,
                user=request.user,
                role__in=[
                    OrganizationMembership.Role.MEMBER,
                    OrganizationMembership.Role.ADMIN,
                    OrganizationMembership.Role.OWNER,
                ],
            ).exists()

        return OrganizationMembership.objects.filter(
            organization=organization,
            user=request.user,
            role__in=[
                OrganizationMembership.Role.ADMIN,
                OrganizationMembership.Role.OWNER,
            ],
        ).exists()
