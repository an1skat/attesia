from rest_framework.permissions import SAFE_METHODS, BasePermission

from app.modules.organizations.models import OrganizationMembership


class IsOrganizationAdminOrOwner(BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        organization = getattr(obj, "organization", obj)
        if not organization:
            return False

        return OrganizationMembership.objects.filter(
            organization=organization,
            user=request.user,
            role__in=["admin", "owner"],
        )
