import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_create_user_with_email_identity():
    User = get_user_model()

    user = User.objects.create_user(
        email="aline@example.ga",
        password="secure-passphrase",
        display_name="Aline NZE",
        account_type=User.AccountType.INDIVIDUAL,
    )

    assert user.email == "aline@example.ga"
    assert user.username is None
    assert user.display_name == "Aline NZE"
    assert user.account_type == User.AccountType.INDIVIDUAL
    assert user.check_password("secure-passphrase")
    assert str(user) == "Aline NZE"


@pytest.mark.django_db
def test_create_superuser_sets_staff_and_superuser_flags():
    User = get_user_model()

    user = User.objects.create_superuser(
        email="admin@bibliogabon.ga",
        password="secure-passphrase",
    )

    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.account_type == User.AccountType.PLATFORM_STAFF
