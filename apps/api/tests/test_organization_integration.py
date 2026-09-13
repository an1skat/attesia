import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from app.modules.organizations.models import Organization, OrganizationMembership

User = get_user_model()

pytestmark = pytest.mark.django_db


def create_user(name):
    return User.objects.create_user(
        email=f"{name}@example.com", display_name=name.title()
    )


def authenticated_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def members_url(organization):
    return reverse("organizations:organization_members", kwargs={"pk": organization.pk})


def member_url(organization, membership):
    return reverse(
        "organizations:organization_member_detail",
        kwargs={"organization_id": organization.pk, "member_id": membership.pk},
    )


def leave_url(organization):
    return reverse(
        "organizations:organization_leave",
        kwargs={"organization_id": organization.pk},
    )


@pytest.fixture
def organization_api():
    owner = create_user("owner")
    client = authenticated_client(owner)
    response = client.post(
        reverse("organizations:organizations"), {"name": "Attesia"}, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED
    return owner, Organization.objects.get(pk=response.data["id"]), client


def test_owner_completes_organization_and_member_lifecycle(organization_api):
    owner, organization, client = organization_api
    member = create_user("member")
    url = members_url(organization)

    response = APIClient().get(
        reverse("organizations:organization_detail", kwargs={"pk": organization.pk})
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Attesia"

    response = APIClient().get(
        reverse("organizations:organizations"), {"search": "attesia"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in response.data["results"]] == [organization.pk]

    response = client.get(reverse("organizations:my_organizations"))
    assert response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in response.data] == [organization.pk]

    response = client.post(url, {"user_id": member.pk, "role": "member"}, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    membership = organization.memberships.get(user=member)
    assert response.data["id"] == membership.pk

    response = APIClient().get(url)

    assert response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in response.data] == sorted(
        item["id"] for item in response.data
    )
    listed = next(item for item in response.data if item["id"] == membership.pk)
    assert listed["user"] == {"id": member.pk, "display_name": member.display_name}
    assert listed["role"] == "member"

    response = client.patch(member_url(organization, membership), {"role": "admin"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["role"] == "admin"
    response = APIClient().get(url)
    listed = next(item for item in response.data if item["id"] == membership.pk)
    assert listed["role"] == "admin"

    response = client.delete(member_url(organization, membership))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    response = APIClient().get(url)
    assert response.status_code == status.HTTP_200_OK
    assert membership.pk not in {item["id"] for item in response.data}
    assert User.objects.filter(pk=member.pk).exists()
    assert Organization.objects.filter(pk=organization.pk).exists()
    assert organization.memberships.filter(user=owner, role="owner").exists()


def test_admin_lifecycle_and_restrictions(organization_api):
    owner, organization, owner_client = organization_api
    admin = create_user("admin")
    other_admin = create_user("other-admin")
    member = create_user("admin-added-member")
    url = members_url(organization)

    admin_response = owner_client.post(
        url, {"user_id": admin.pk, "role": "admin"}, format="json"
    )
    other_admin_response = owner_client.post(
        url, {"user_id": other_admin.pk, "role": "admin"}, format="json"
    )
    assert admin_response.status_code == status.HTTP_201_CREATED
    assert other_admin_response.status_code == status.HTTP_201_CREATED

    admin_membership = organization.memberships.get(user=admin)
    other_admin_membership = organization.memberships.get(user=other_admin)
    owner_membership = organization.memberships.get(user=owner)
    admin_client = authenticated_client(admin)

    response = admin_client.post(
        url, {"user_id": member.pk, "role": "member"}, format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    member_membership = organization.memberships.get(user=member)
    response = admin_client.delete(member_url(organization, member_membership))
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = admin_client.patch(
        member_url(organization, other_admin_membership), {"role": "member"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    for protected in (other_admin_membership, owner_membership, admin_membership):
        response = admin_client.delete(member_url(organization, protected))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    assert not organization.memberships.filter(pk=member_membership.pk).exists()
    assert organization.memberships.filter(
        pk=admin_membership.pk, role="admin"
    ).exists()
    assert organization.memberships.filter(
        pk=other_admin_membership.pk, role="admin"
    ).exists()
    assert organization.memberships.filter(
        pk=owner_membership.pk, role="owner"
    ).exists()


def test_member_restrictions_and_leave(organization_api):
    owner, organization, owner_client = organization_api
    member = create_user("member")
    target = create_user("target")
    candidate = create_user("candidate")
    url = members_url(organization)
    member_response = owner_client.post(
        url, {"user_id": member.pk, "role": "member"}, format="json"
    )
    target_response = owner_client.post(
        url, {"user_id": target.pk, "role": "member"}, format="json"
    )
    assert member_response.status_code == status.HTTP_201_CREATED
    assert target_response.status_code == status.HTTP_201_CREATED
    member_membership = organization.memberships.get(user=member)
    target_membership = organization.memberships.get(user=target)
    member_client = authenticated_client(member)

    response = member_client.post(
        url, {"user_id": candidate.pk, "role": "member"}, format="json"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    response = member_client.patch(
        member_url(organization, target_membership), {"role": "admin"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    response = member_client.delete(member_url(organization, target_membership))
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = member_client.post(leave_url(organization))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not organization.memberships.filter(pk=member_membership.pk).exists()
    assert organization.memberships.filter(pk=target_membership.pk).exists()
    assert organization.memberships.filter(user=owner, role="owner").exists()
    assert User.objects.filter(pk=member.pk).exists()
    assert Organization.objects.filter(pk=organization.pk).exists()


def test_owner_role_and_membership_are_protected(organization_api):
    owner, organization, client = organization_api
    candidate = create_user("candidate")
    url = members_url(organization)

    response = client.post(
        url, {"user_id": candidate.pk, "role": "owner"}, format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not organization.memberships.filter(user=candidate).exists()

    response = client.post(
        url, {"user_id": candidate.pk, "role": "member"}, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED
    membership = organization.memberships.get(user=candidate)
    owner_membership = organization.memberships.get(user=owner)

    response = client.patch(member_url(organization, membership), {"role": "owner"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    response = client.patch(
        member_url(organization, owner_membership), {"role": "member"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    response = client.delete(member_url(organization, owner_membership))
    assert response.status_code == status.HTTP_403_FORBIDDEN
    response = client.post(leave_url(organization))
    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert organization.memberships.get(pk=membership.pk).role == "member"
    assert organization.memberships.get(pk=owner_membership.pk).role == "owner"


def test_membership_ids_are_isolated_by_organization(organization_api):
    owner, first, client = organization_api
    response = client.post(
        reverse("organizations:organizations"), {"name": "Other"}, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED
    second = Organization.objects.get(pk=response.data["id"])
    first_member = create_user("first-member")
    second_member = create_user("second-member")
    first_response = client.post(
        members_url(first),
        {"user_id": first_member.pk, "role": "member"},
        format="json",
    )
    second_response = client.post(
        members_url(second),
        {"user_id": second_member.pk, "role": "member"},
        format="json",
    )
    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_201_CREATED
    first_membership = first.memberships.get(user=first_member)

    cross_organization_url = member_url(second, first_membership)
    response = client.patch(cross_organization_url, {"role": "admin"})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Membership does not exist."}
    response = client.delete(cross_organization_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Membership does not exist."}

    response = APIClient().get(members_url(second))
    assert response.status_code == status.HTTP_200_OK
    listed_user_ids = {item["user"]["id"] for item in response.data}
    assert listed_user_ids == {owner.pk, second_member.pk}
    assert first_member.pk not in listed_user_ids
    first_membership.refresh_from_db()
    assert first_membership.role == "member"


def test_duplicate_membership_has_stable_api_error_and_database_protection(
    organization_api,
):
    _, organization, client = organization_api
    member = create_user("duplicate")
    url = members_url(organization)

    response = client.post(url, {"user_id": member.pk, "role": "member"}, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    membership = organization.memberships.get(user=member)

    response = client.post(url, {"user_id": member.pk, "role": "admin"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == ["User is already an organization member."]
    assert response.data[0].code == "membership_exists"
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganizationMembership.objects.create(
            organization=organization, user=member, role="admin"
        )
    membership.refresh_from_db()
    assert membership.role == "member"
    assert organization.memberships.filter(user=member).count() == 1


def test_membership_mutations_require_authentication(organization_api):
    _, organization, _ = organization_api
    member = create_user("member")
    candidate = create_user("candidate")
    membership = OrganizationMembership.objects.create(
        organization=organization, user=member, role="member"
    )
    client = APIClient()
    requests = (
        (
            "post",
            members_url(organization),
            {"user_id": candidate.pk, "role": "member"},
        ),
        ("patch", member_url(organization, membership), {"role": "admin"}),
        ("delete", member_url(organization, membership), None),
        ("post", leave_url(organization), None),
    )

    for method, url, data in requests:
        response = getattr(client, method)(url, data, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    assert organization.memberships.filter(pk=membership.pk, role="member").exists()
    assert not organization.memberships.filter(user=candidate).exists()


def test_missing_membership_resources_return_not_found(organization_api):
    _, organization, client = organization_api
    candidate = create_user("candidate")
    missing_organization_id = organization.pk + 1000
    missing_membership_id = organization.memberships.order_by("pk").last().pk + 1000
    missing_members_url = reverse(
        "organizations:organization_members", kwargs={"pk": missing_organization_id}
    )
    missing_member_url = reverse(
        "organizations:organization_member_detail",
        kwargs={
            "organization_id": organization.pk,
            "member_id": missing_membership_id,
        },
    )

    response = client.post(
        missing_members_url,
        {"user_id": candidate.pk, "role": "member"},
        format="json",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response = client.patch(missing_member_url, {"role": "admin"}, format="json")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response = client.delete(missing_member_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response = APIClient().get(missing_members_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

    assert not organization.memberships.filter(user=candidate).exists()
    assert organization.memberships.filter(role="owner").count() == 1
