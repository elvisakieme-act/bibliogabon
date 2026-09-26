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


@pytest.mark.django_db
def test_content_admin_is_distinct_from_platform_staff():
    """Le moderateur de contenu a un perimetre borne : valider metadonnees,
    droits, statut et publication. Le confondre avec le staff plateforme lui
    donnerait la facturation et la configuration."""
    User = get_user_model()

    reviewer = User.objects.create_user(
        email="moderation@bibliogabon.ga",
        password="secure-passphrase",
        display_name="Moderation",
        account_type=User.AccountType.CONTENT_ADMIN,
    )

    assert reviewer.account_type == User.AccountType.CONTENT_ADMIN
    assert reviewer.account_type != User.AccountType.PLATFORM_STAFF
    assert reviewer.is_superuser is False


def test_account_type_covers_every_product_actor():
    """Les sept acteurs du document produit se projettent sur ces valeurs,
    plus le role d'adhesion pour la portee organisationnelle."""
    User = get_user_model()

    assert set(User.AccountType.values) == {
        "individual",
        "teacher_author",
        "organization_admin",
        "content_admin",
        "platform_staff",
    }


@pytest.mark.django_db
def test_create_superuser_still_yields_platform_staff():
    """La promotion en moderateur de contenu doit rester un acte delibere :
    aucun compte existant ne change de sens."""
    User = get_user_model()

    admin = User.objects.create_superuser(
        email="root@bibliogabon.ga", password="secure-passphrase"
    )

    assert admin.account_type == User.AccountType.PLATFORM_STAFF
    assert admin.is_superuser is True
