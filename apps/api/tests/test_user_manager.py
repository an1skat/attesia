import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_create_user():
    user = User.objects.create_user(
        email="Alice@EXAMPLE.COM",
        password="secret-password",
        display_name="Alice",
    )

    assert user.pk is not None
    assert user.email == "Alice@example.com"
    assert user.password != "secret-password"
    assert user.check_password("secret-password")
    assert user.get_full_name() == "Alice"
    assert user.get_short_name() == "Alice"


@pytest.mark.parametrize("email", [None, ""])
def test_create_user_requires_email(email):
    with pytest.raises(ValueError, match="Email must be set"):
        User.objects.create_user(
            email=email,
            password="secret-password",
            display_name="Alice",
        )


@pytest.mark.django_db
def test_create_superuser():
    user = User.objects.create_superuser(
        email="admin@example.com",
        password="secret-password",
        display_name="Admin",
    )

    assert user.pk is not None
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.check_password("secret-password")


@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_create_superuser_rejects_false_flags(flag):
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="admin@example.com",
            password="secret-password",
            display_name="Admin",
            **{flag: False},
        )
