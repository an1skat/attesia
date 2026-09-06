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


@pytest.mark.parametrize(
    "viewer", ["anonymous", "outsider", "owner", "admin", "member"]
)
def test_get_organization_returns_public_fields(owner, viewer):
    create_organization(owner=owner, name="Another organization")
    organization = create_organization(owner=owner, name="Attesia")
    client = APIClient()
    if viewer != "anonymous":
        user = owner
        if viewer != "owner":
            user = User.objects.create_user(
                email="viewer@example.com", display_name="Viewer"
            )
        if viewer in ("admin", "member"):
            OrganizationMembership.objects.create(
                user=user, organization=organization, role=viewer
            )
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    url = reverse("organizations:organization_detail", kwargs={"pk": organization.pk})
    assert url == f"/api/v1/organizations/{organization.pk}/"

    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data) == {"id", "name", "created_at", "updated_at"}
    assert response.data["id"] == organization.pk
    assert response.data["name"] == "Attesia"
    assert response.data["created_at"]
    assert response.data["updated_at"]


@pytest.mark.parametrize("authenticated", [False, True])
def test_get_missing_organization_returns_404(client, owner, authenticated):
    organization = create_organization(owner=owner, name="Attesia")
    missing_id = organization.pk
    organization.delete()
    if not authenticated:
        client.credentials()

    response = client.get(
        reverse("organizations:organization_detail", kwargs={"pk": missing_id})
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("organization_id", ["invalid", "-1", "9223372036854775808"])
def test_get_organization_with_invalid_id_returns_404(organization_id):
    response = APIClient().get(f"/api/v1/organizations/{organization_id}/")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("authenticated", [False, True])
def test_list_organizations_is_public(client, owner, url, authenticated):
    other = User.objects.create_user(email="other@example.com", display_name="Other")
    first = create_organization(owner=owner, name="Z")
    second = create_organization(owner=other, name="A")
    if not authenticated:
        client.credentials()

    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2
    assert response.data["next"] is None
    assert response.data["previous"] is None
    assert [item["id"] for item in response.data["results"]] == [first.pk, second.pk]
    for item in response.data["results"]:
        assert set(item) == {"id", "name", "created_at", "updated_at"}


@pytest.mark.parametrize(
    "search, expected_names",
    [
        ("tEs", ["Attesia Events", "Attesia Music"]),
        ("  attesia  ", ["Attesia Events", "Attesia Music"]),
        ("attesia music", ["Attesia Music"]),
        ("КИЇВ", ["Музичний Київ"]),
        ("missing", []),
        ("owner@example.com", []),
        ("", ["Attesia Events", "Attesia Music", "Музичний Київ"]),
        ("   ", ["Attesia Events", "Attesia Music", "Музичний Київ"]),
    ],
)
def test_search_organizations_by_name(owner, url, search, expected_names):
    for name in ["Attesia Events", "Attesia Music", "Музичний Київ"]:
        create_organization(owner=owner, name=name)

    response = APIClient().get(url, {"search": search})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == len(expected_names)
    assert [item["name"] for item in response.data["results"]] == expected_names


def test_list_organizations_paginates_search_in_stable_order(owner, url):
    create_organization(owner=owner, name="Unrelated")
    organizations = [
        create_organization(owner=owner, name="Attesia") for _ in range(21)
    ]
    create_organization(owner=owner, name="Another unrelated organization")
    client = APIClient()

    first = client.get(url, {"search": "attesia"})

    assert first.status_code == status.HTTP_200_OK
    assert first.data["count"] == 21
    assert first.data["previous"] is None
    assert first.data["next"] is not None
    assert [item["id"] for item in first.data["results"]] == [
        organization.pk for organization in organizations[:20]
    ]

    second = client.get(first.data["next"])

    assert second.status_code == status.HTTP_200_OK
    assert second.data["count"] == 21
    assert second.data["next"] is None
    assert second.data["previous"] is not None
    assert [item["id"] for item in second.data["results"]] == [organizations[20].pk]
    assert client.get(second.data["previous"]).data == first.data


def test_list_organizations_returns_empty_page(url):
    response = APIClient().get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"count": 0, "next": None, "previous": None, "results": []}


@pytest.mark.parametrize("page", ["0", "-1", "invalid", "2"])
def test_list_organizations_rejects_invalid_or_missing_page(url, page):
    response = APIClient().get(url, {"page": page})

    assert response.status_code == status.HTTP_404_NOT_FOUND
