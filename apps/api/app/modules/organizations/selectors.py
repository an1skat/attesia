from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from .models import Organization, OrganizationMembership

User = get_user_model()


def get_user_organizations(*, user: User) -> QuerySet[Organization]:
    return Organization.objects.filter(memberships__user=user).order_by("pk")


def get_organization_memberships(
    *, organization_id: int
) -> QuerySet[OrganizationMembership]:
    organization = Organization.objects.get(pk=organization_id)
    return organization.memberships.select_related("user").order_by("pk")
