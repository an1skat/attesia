from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.organizations.services import create_organization

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_create_organization_with_owner():
    owner = User.objects.create_user(email="owner@example.com", display_name="Owner")

    organization = create_organization(owner=owner, name=" \tOpenAI\n\u00a0")

    assert Organization.objects.get() == organization
    organization.refresh_from_db()
    assert organization.name == "OpenAI"
    membership = OrganizationMembership.objects.get()
    assert membership.organization == organization
    assert membership.user == owner
    assert membership.role == OrganizationMembership.Role.OWNER


@pytest.mark.parametrize("name", ["", "   ", "\t\n\u00a0", "a" * 256])
def test_create_organization_rejects_invalid_name(name):
    owner = User.objects.create_user(email="owner@example.com", display_name="Owner")

    with pytest.raises(ValidationError) as error:
        create_organization(owner=owner, name=name)

    assert "name" in error.value.message_dict
    assert not Organization.objects.exists()
    assert not OrganizationMembership.objects.exists()


def test_create_organization_rolls_back_if_membership_fails():
    owner = User.objects.create_user(email="owner@example.com", display_name="Owner")

    def fail_membership(**kwargs):
        assert Organization.objects.filter(pk=kwargs["organization"].pk).exists()
        raise IntegrityError("Membership creation failed")

    with (
        patch.object(
            OrganizationMembership.objects, "create", side_effect=fail_membership
        ),
        pytest.raises(IntegrityError, match="Membership creation failed"),
    ):
        create_organization(owner=owner, name="OpenAI")

    assert not Organization.objects.exists()
    assert not OrganizationMembership.objects.exists()
    assert User.objects.filter(pk=owner.pk).exists()


@pytest.mark.parametrize("name", ["OpenAI", "openai", " OPENAI\t"])
def test_create_organization_allows_duplicate_names(name):
    first_owner = User.objects.create_user(
        email="first@example.com", display_name="First"
    )
    other_owner = User.objects.create_user(
        email="other@example.com", display_name="Other"
    )
    organization = create_organization(owner=first_owner, name="OpenAI")

    other_organization = create_organization(owner=other_owner, name=name)

    assert other_organization.pk != organization.pk
    assert other_organization.name == name.strip()
    assert Organization.objects.count() == 2
    assert OrganizationMembership.objects.count() == 2
    assert organization.memberships.get().user == first_owner
    assert other_organization.memberships.get().user == other_owner
