from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from psycopg.errors import UniqueViolation

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


def add_organization_member(
    *, actor: User, organization_id: int, user_id: int, role: str
) -> OrganizationMembership:
    if role not in (
        OrganizationMembership.Role.ADMIN,
        OrganizationMembership.Role.MEMBER,
    ):
        raise ValidationError(
            "Only admin or member roles can be added.", code="invalid_role"
        )

    try:
        organization = Organization.objects.get(pk=organization_id)
    except Organization.DoesNotExist as exc:
        raise ValidationError(
            "Organization does not exist.", code="organization_not_found"
        ) from exc

    if not organization.memberships.filter(
        user_id=actor.pk,
        role__in=(OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN),
    ).exists():
        raise PermissionDenied("Only owners and admins can add organization members.")

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise ValidationError("User does not exist.", code="user_not_found") from exc

    try:
        with transaction.atomic():
            return OrganizationMembership.objects.create(
                organization=organization, user=user, role=role
            )
    except IntegrityError as exc:
        if (
            isinstance(exc.__cause__, UniqueViolation)
            and exc.__cause__.diag.constraint_name == "unique_organization_membership"
        ):
            raise ValidationError(
                "User is already an organization member.", code="membership_exists"
            ) from exc
        raise
