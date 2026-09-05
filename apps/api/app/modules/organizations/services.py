from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Organization, OrganizationMembership

User = get_user_model()


@transaction.atomic
def create_organization(*, owner: User, name: str) -> Organization:
    organization = Organization(name=name.strip())
    organization.clean_fields()
    organization.save()
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrganizationMembership.Role.OWNER,
    )
    return organization
