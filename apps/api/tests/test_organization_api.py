from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.organizations.services import create_organization

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return User.objects.create_user(
        email="owner@example.com",
        display_name="Owner",
    )


@pytest.fixture
def client(owner):
    client = APIClient()
    token = str(AccessToken.for_user(owner))
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def url():
    return reverse("organizations:organizations")


@pytest.fixture
def my_organizations_url():
    url = reverse("organizations:my_organizations")
    assert url == "/api/v1/me/organizations/"
    return url


def test_create_organization(client, owner, url):
    response = client.post(url, {"name": " \tAttesia\n"}, format="json")

    assert response.status_code == status.HTTP_201_CREATED

    organization = Organization.objects.get()
    assert organization.name == "Attesia"
    assert response.data["id"] == organization.pk
    assert response.data["name"] == organization.name
    assert response.data["created_at"]
    assert response.data["updated_at"]
    assert set(response.data) == {"id", "name", "created_at", "updated_at"}

    membership = OrganizationMembership.objects.get()
    assert membership.organization == organization
    assert membership.user == owner
    assert membership.role == OrganizationMembership.Role.OWNER


@pytest.mark.parametrize("token", [None, "invalid-token"])
def test_create_organization_requires_authentication(url, token):
    client = APIClient()
    if token is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.post(url, {"name": "Attesia"}, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not Organization.objects.exists()
    assert not OrganizationMembership.objects.exists()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": " \t\n\u00a0"},
        {"name": None},
        {"name": "a" * 256},
    ],
)
def test_create_organization_rejects_invalid_name(client, url, payload):
    response = client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "name" in response.data
    assert not Organization.objects.exists()
    assert not OrganizationMembership.objects.exists()


def test_client_cannot_choose_owner(client, owner, url):
    other_user = User.objects.create_user(
        email="other@example.com",
        display_name="Other",
    )

    response = client.post(
        url,
        {
            "name": "Attesia",
            "owner_id": other_user.pk,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    membership = OrganizationMembership.objects.get()
    assert membership.organization_id == response.data["id"]
    assert membership.user == owner
    assert membership.role == OrganizationMembership.Role.OWNER
    assert not other_user.organization_memberships.exists()


def test_create_organization_allows_duplicate_names(client, owner, url):
    first = client.post(url, {"name": "Attesia"}, format="json")
    second = client.post(url, {"name": "Attesia"}, format="json")

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_201_CREATED
    assert first.data["id"] != second.data["id"]
    assert Organization.objects.filter(name="Attesia").count() == 2
    assert (
        OrganizationMembership.objects.filter(
            user=owner,
            role=OrganizationMembership.Role.OWNER,
        ).count()
        == 2
    )


def test_membership_failure_rolls_back_organization(client, url):
    with (
        patch.object(
            OrganizationMembership.objects,
            "create",
            side_effect=IntegrityError("Membership creation failed"),
        ),
        pytest.raises(IntegrityError, match="Membership creation failed"),
    ):
        client.post(url, {"name": "Attesia"}, format="json")

    assert not Organization.objects.exists()
    assert not OrganizationMembership.objects.exists()


def test_list_my_organizations_returns_only_current_user_memberships(
    client, owner, my_organizations_url
):
    other = User.objects.create_user(email="other@example.com", display_name="Other")
    first = create_organization(owner=owner, name="A")
    second = create_organization(owner=other, name="B")
    create_organization(owner=other, name="C")
    OrganizationMembership.objects.create(
        user=owner, organization=second, role=OrganizationMembership.Role.MEMBER
    )

    response = client.get(my_organizations_url)

    assert response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in response.data] == [first.pk, second.pk]
    assert [item["name"] for item in response.data] == ["A", "B"]


def test_list_my_organizations_is_empty_without_membership(
    client, my_organizations_url
):
    other = User.objects.create_user(email="other@example.com", display_name="Other")
    create_organization(owner=other, name="C")

    response = client.get(my_organizations_url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


@pytest.mark.parametrize(
    "token", [None, "invalid-token"], ids=["no_credentials", "invalid_credentials"]
)
def test_list_my_organizations_requires_authentication(my_organizations_url, token):
    client = APIClient()
    if token is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.get(my_organizations_url)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
