import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from app.modules.organizations.models import Organization, OrganizationMembership

User = get_user_model()


def create_user(email):
    return User.objects.create_user(email=email, display_name=email)


@pytest.mark.django_db
def test_create_organization():
    organization = Organization.objects.create(name="Attesia")

    assert organization.pk is not None
    assert organization.name == "Attesia"
    assert organization.created_at is not None
    assert organization.updated_at is not None


@pytest.mark.django_db
def test_create_organization_membership():
    user = create_user("owner@example.com")
    organization = Organization.objects.create(name="Attesia")

    membership = OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrganizationMembership.Role.OWNER,
    )

    assert membership.pk is not None
    assert membership.user == user
    assert membership.organization == organization
    assert membership.role == OrganizationMembership.Role.OWNER
    assert membership.created_at is not None


@pytest.mark.django_db
def test_user_can_belong_to_multiple_organizations():
    user = create_user("member@example.com")
    organizations = [
        Organization.objects.create(name="First"),
        Organization.objects.create(name="Second"),
    ]

    for organization in organizations:
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrganizationMembership.Role.MEMBER,
        )

    assert user.organization_memberships.count() == 2


@pytest.mark.django_db
def test_organization_can_have_multiple_users():
    organization = Organization.objects.create(name="Attesia")
    users = [
        create_user("first@example.com"),
        create_user("second@example.com"),
    ]

    for user in users:
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrganizationMembership.Role.MEMBER,
        )

    assert organization.memberships.count() == 2


@pytest.mark.django_db
def test_user_cannot_have_duplicate_organization_membership():
    user = create_user("member@example.com")
    organization = Organization.objects.create(name="Attesia")
    membership = {
        "user": user,
        "organization": organization,
        "role": OrganizationMembership.Role.MEMBER,
    }
    OrganizationMembership.objects.create(**membership)

    with pytest.raises(IntegrityError), transaction.atomic():
        OrganizationMembership.objects.create(**membership)


@pytest.mark.django_db
def test_membership_requires_valid_role():
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganizationMembership.objects.create(
            user=create_user("member@example.com"),
            organization=Organization.objects.create(name="Attesia"),
        )


@pytest.mark.django_db
@pytest.mark.parametrize("role", OrganizationMembership.Role.values)
def test_membership_roles_are_valid(role):
    membership = OrganizationMembership(
        user=create_user(f"{role}@example.com"),
        organization=Organization.objects.create(name=f"{role.title()} organization"),
        role=role,
    )

    membership.full_clean()
    membership.save()

    assert membership.role == role
