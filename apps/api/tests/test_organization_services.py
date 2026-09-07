from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction

from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.organizations.services import (
    add_organization_member,
    create_organization,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_create_organization_with_owner():
    owner = User.objects.create_user(email="owner@example.com", display_name="Owner")

    organization = create_organization(owner=owner, name=" \tattesia\n\u00a0")

    assert Organization.objects.get() == organization
    organization.refresh_from_db()
    assert organization.name == "attesia"
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
        create_organization(owner=owner, name="attesia")

    assert not Organization.objects.exists()
    assert not OrganizationMembership.objects.exists()
    assert User.objects.filter(pk=owner.pk).exists()


@pytest.mark.parametrize("name", ["Attesia", "attesia", " ATTESIA\t"])
def test_create_organization_allows_duplicate_names(name):
    first_owner = User.objects.create_user(
        email="first@example.com", display_name="First"
    )
    other_owner = User.objects.create_user(
        email="other@example.com", display_name="Other"
    )
    organization = create_organization(owner=first_owner, name="attesia")

    other_organization = create_organization(owner=other_owner, name=name)

    assert other_organization.pk != organization.pk
    assert other_organization.name == name.strip()
    assert Organization.objects.count() == 2
    assert OrganizationMembership.objects.count() == 2
    assert organization.memberships.get().user == first_owner
    assert other_organization.memberships.get().user == other_owner


@pytest.fixture
def membership_args():
    owner = User.objects.create_user(email="owner@example.com", display_name="Owner")
    organization = create_organization(owner=owner, name="Attesia")
    target = User.objects.create_user(email="target@example.com", display_name="Target")
    return {
        "actor": owner,
        "organization_id": organization.pk,
        "user_id": target.pk,
        "role": OrganizationMembership.Role.MEMBER,
    }


@pytest.mark.parametrize("actor_role", ["owner", "admin"])
@pytest.mark.parametrize("role", ["member", "admin"])
def test_add_organization_member(membership_args, actor_role, role):
    OrganizationMembership.objects.update(role=actor_role)
    membership_args["role"] = role

    membership = add_organization_member(**membership_args)

    membership.refresh_from_db()
    assert membership.organization_id == membership_args["organization_id"]
    assert membership.user_id == membership_args["user_id"]
    assert membership.role == role
    assert membership.created_at is not None
    assert OrganizationMembership.objects.count() == 2
    assert (
        OrganizationMembership.objects.get(user=membership_args["actor"]).role
        == actor_role
    )


@pytest.mark.parametrize("actor_role", ["owner", "admin"])
@pytest.mark.parametrize("role", ["owner", "invalid", "", None])
def test_add_organization_member_rejects_invalid_role(
    membership_args, actor_role, role
):
    OrganizationMembership.objects.update(role=actor_role)
    membership_args["role"] = role
    before = list(OrganizationMembership.objects.values())

    with pytest.raises(ValidationError) as error:
        add_organization_member(**membership_args)

    assert error.value.code == "invalid_role"
    assert list(OrganizationMembership.objects.values()) == before


@pytest.mark.parametrize("actor_role", ["member", "outsider"])
def test_add_organization_member_requires_permission(membership_args, actor_role):
    if actor_role == "outsider":
        other = create_organization(owner=membership_args["actor"], name="Other")
        OrganizationMembership.objects.exclude(organization=other).delete()
    else:
        OrganizationMembership.objects.update(role=actor_role)
    before = list(OrganizationMembership.objects.values())

    with pytest.raises(PermissionDenied):
        add_organization_member(**membership_args)

    assert list(OrganizationMembership.objects.values()) == before


def test_add_duplicate_member_keeps_outer_transaction_usable(membership_args):
    membership = add_organization_member(**membership_args)
    membership_args["role"] = OrganizationMembership.Role.ADMIN

    with transaction.atomic():
        with pytest.raises(ValidationError) as error:
            add_organization_member(**membership_args)

        assert error.value.code == "membership_exists"
        assert isinstance(error.value.__cause__, IntegrityError)
        membership.refresh_from_db()
        assert membership.role == OrganizationMembership.Role.MEMBER
        assert OrganizationMembership.objects.count() == 2
        Organization.objects.create(name="Transaction still works")

    assert Organization.objects.filter(name="Transaction still works").exists()
    assert (
        OrganizationMembership.objects.filter(
            organization_id=membership_args["organization_id"],
            user_id=membership_args["user_id"],
        ).get()
        == membership
    )


@pytest.mark.parametrize("missing", ["organization", "user"])
def test_add_organization_member_rejects_missing_object(membership_args, missing):
    if missing == "organization":
        Organization.objects.filter(pk=membership_args["organization_id"]).delete()
    else:
        User.objects.filter(pk=membership_args["user_id"]).delete()
    before = list(OrganizationMembership.objects.values())

    with pytest.raises(ValidationError) as error:
        add_organization_member(**membership_args)

    assert error.value.code == f"{missing}_not_found"
    assert list(OrganizationMembership.objects.values()) == before


@pytest.mark.django_db(transaction=True)
def test_concurrent_add_organization_member(membership_args):
    assert connection.vendor == "postgresql"
    barrier = Barrier(2, timeout=10)

    def synchronize_inserts(execute, sql, params, many, context):
        if sql.startswith("INSERT INTO"):
            barrier.wait()
        return execute(sql, params, many, context)

    def add_member():
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL statement_timeout = '15s'")
                with connection.execute_wrapper(synchronize_inserts):
                    try:
                        add_organization_member(**membership_args)
                    except ValidationError as error:
                        outcome = error.code
                    else:
                        outcome = "created"
                # Both connections must remain usable after the concurrent insert.
                assert (
                    OrganizationMembership.objects.filter(
                        organization_id=membership_args["organization_id"],
                        user_id=membership_args["user_id"],
                    ).count()
                    == 1
                )
            return outcome
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(add_member) for _ in range(2)]
        outcomes = [future.result(timeout=20) for future in futures]

    assert sorted(outcomes) == ["created", "membership_exists"]
    membership = OrganizationMembership.objects.get(
        organization_id=membership_args["organization_id"],
        user_id=membership_args["user_id"],
    )
    assert membership.role == OrganizationMembership.Role.MEMBER
    assert OrganizationMembership.objects.count() == 2
    assert (
        OrganizationMembership.objects.get(user=membership_args["actor"]).role
        == "owner"
    )
