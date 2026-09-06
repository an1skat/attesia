import pytest
from django.contrib.auth import get_user_model

from app.modules.organizations.models import OrganizationMembership
from app.modules.organizations.selectors import get_user_organizations
from app.modules.organizations.services import create_organization

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_selectors_return_only_user_organizations(django_assert_num_queries):
    user = User.objects.create_user(email="user@example.com", display_name="User")
    other = User.objects.create_user(email="other@example.com", display_name="Other")
    first = create_organization(owner=user, name="A")
    second = create_organization(owner=other, name="B")
    create_organization(owner=other, name="C")
    OrganizationMembership.objects.create(
        user=user, organization=second, role=OrganizationMembership.Role.MEMBER
    )

    with django_assert_num_queries(1):
        assert list(get_user_organizations(user=user)) == [first, second]


def test_selectors_return_no_organizations_without_membership():
    user = User.objects.create_user(email="user@example.com", display_name="User")
    other = User.objects.create_user(email="other@example.com", display_name="Other")
    create_organization(owner=other, name="A")

    assert list(get_user_organizations(user=user)) == []


def test_get_user_organizations_requires_user():
    with pytest.raises(TypeError, match="user"):
        get_user_organizations()
