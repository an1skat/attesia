from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from django.utils.dateparse import parse_datetime
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


@pytest.mark.parametrize("authenticated", [False, True])
def test_list_organization_members_is_public(
    client, owner, authenticated, django_assert_num_queries
):
    organization = Organization.objects.create(name="Attesia")
    memberships = []
    for pk, role in zip((30, 10, 20), OrganizationMembership.Role.values):
        user = User.objects.create_user(
            email=f"{role}@members.example.com", display_name=role.title()
        )
        memberships.append(
            OrganizationMembership.objects.create(
                pk=pk, user=user, organization=organization, role=role
            )
        )
    create_organization(owner=owner, name="Another organization")
    if not authenticated:
        client.credentials()
    url = reverse("organizations:organization_members", kwargs={"pk": organization.pk})
    assert url == f"/api/v1/organizations/{organization.pk}/members/"

    with django_assert_num_queries(3 if authenticated else 2):
        response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert [item["id"] for item in data] == [10, 20, 30]
    for item, membership in zip(data, sorted(memberships, key=lambda item: item.pk)):
        assert set(item) == {"id", "user", "role", "created_at"}
        assert item["user"] == {
            "id": membership.user_id,
            "display_name": membership.user.display_name,
        }
        assert item["role"] == membership.role
        assert parse_datetime(item["created_at"]) == membership.created_at


@pytest.mark.parametrize("authenticated", [False, True])
def test_list_missing_organization_members_returns_404(client, owner, authenticated):
    organization = create_organization(owner=owner, name="Attesia")
    missing_id = organization.pk
    organization.delete()
    if not authenticated:
        client.credentials()

    response = client.get(
        reverse("organizations:organization_members", kwargs={"pk": missing_id})
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_list_organization_members_returns_empty_list():
    organization = Organization.objects.create(name="Empty")

    response = APIClient().get(
        reverse("organizations:organization_members", kwargs={"pk": organization.pk})
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


@pytest.fixture
def organization(owner):
    return create_organization(owner=owner, name="Attesia")


@pytest.fixture
def target_user():
    return User.objects.create_user(email="target@example.com", display_name="Target")


@pytest.fixture
def members_url(organization):
    return reverse("organizations:organization_members", kwargs={"pk": organization.pk})


@pytest.mark.parametrize("actor_role", ["owner", "admin"])
@pytest.mark.parametrize("role", ["member", "admin"])
def test_post_organization_member(
    client, organization, target_user, members_url, actor_role, role
):
    if actor_role == "admin":
        admin = User.objects.create_user(
            email="admin@example.com", display_name="Admin"
        )
        OrganizationMembership.objects.create(
            organization=organization, user=admin, role="admin"
        )
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(admin)}")
    before_count = organization.memberships.count()

    response = client.post(
        members_url, {"user_id": target_user.pk, "role": role}, format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    membership = organization.memberships.get(user=target_user)
    assert membership.role == role
    assert organization.memberships.count() == before_count + 1
    data = response.json()
    assert set(data) == {"id", "user", "role", "created_at"}
    assert data["id"] == membership.pk
    assert data["user"] == {
        "id": target_user.pk,
        "display_name": target_user.display_name,
    }
    assert data["role"] == role
    assert parse_datetime(data["created_at"]) == membership.created_at
    listing = APIClient().get(members_url)
    assert listing.status_code == status.HTTP_200_OK
    assert data in listing.json()


@pytest.mark.parametrize("actor_role", ["member", "outsider"])
def test_post_organization_member_forbidden(
    client, owner, organization, target_user, members_url, actor_role
):
    actor = User.objects.create_user(email="actor@example.com", display_name="Actor")
    if actor_role == "member":
        OrganizationMembership.objects.create(
            organization=organization, user=actor, role=actor_role
        )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(actor)}")
    before = list(organization.memberships.order_by("pk").values())

    response = client.post(
        members_url,
        {"user_id": target_user.pk, "role": "member", "actor": owner.pk},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert list(organization.memberships.order_by("pk").values()) == before


@pytest.mark.parametrize("token", [None, "invalid-token"])
def test_post_organization_member_requires_authentication(
    organization, target_user, members_url, token
):
    client = APIClient()
    if token is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.post(
        members_url, {"user_id": target_user.pk, "role": "member"}, format="json"
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert organization.memberships.count() == 1
    assert not organization.memberships.filter(user=target_user).exists()


def test_post_duplicate_organization_member(
    client, organization, target_user, members_url
):
    first = client.post(
        members_url, {"user_id": target_user.pk, "role": "member"}, format="json"
    )
    assert first.status_code == status.HTTP_201_CREATED

    response = client.post(
        members_url, {"user_id": target_user.pk, "role": "admin"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data[0].code == "membership_exists"
    membership = organization.memberships.get(user=target_user)
    assert membership.pk == first.data["id"]
    assert membership.role == "member"
    assert organization.memberships.count() == 2


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"user_id": 1},
        {"role": "member"},
        {"user_id": 1, "role": "owner"},
        {"user_id": 1, "role": "invalid"},
        {"user_id": 1, "role": ""},
        {"user_id": 1, "role": None},
        {"user_id": None, "role": "member"},
        {"user_id": "invalid", "role": "member"},
        {"user_id": 1.5, "role": "member"},
        {"user_id": True, "role": "member"},
        {"user_id": 0, "role": "member"},
        {"user_id": -1, "role": "member"},
        [],
    ],
)
def test_post_organization_member_rejects_invalid_input(
    client, organization, members_url, payload
):
    before = list(organization.memberships.values())

    response = client.post(members_url, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert list(organization.memberships.values()) == before


@pytest.mark.parametrize("missing", ["organization", "user"])
def test_post_organization_member_not_found(
    client, organization, target_user, members_url, missing
):
    user_id = target_user.pk
    if missing == "organization":
        organization.delete()
    else:
        target_user.delete()
    before = list(OrganizationMembership.objects.values())

    response = client.post(
        members_url, {"user_id": user_id, "role": "member"}, format="json"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data["detail"].code == f"{missing}_not_found"
    assert list(OrganizationMembership.objects.values()) == before


def test_post_organization_member_uses_url_and_authenticated_actor(
    client, owner, organization, target_user, members_url
):
    other = create_organization(owner=owner, name="Other")

    response = client.post(
        members_url,
        {
            "user_id": target_user.pk,
            "role": "member",
            "organization_id": other.pk,
            "actor": target_user.pk,
            "user": owner.pk,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert organization.memberships.get(user=target_user).pk == response.data["id"]
    assert organization.memberships.count() == 2
    assert other.memberships.count() == 1
    assert other.memberships.get().user == owner
