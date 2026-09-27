from __future__ import annotations

import pytest
from django.contrib import admin
from django.test import RequestFactory

from accounts.models import Organization, User
from billing.models import CommercialOffer, PaymentTransaction, Subscription
from catalog.models import Document, RightsAgreement
from operations.models import AuditLog, PublicationReview, SupportTicket


CONTENT_MODELS = [Document, RightsAgreement, PublicationReview, SupportTicket]
PLATFORM_MODELS = [CommercialOffer, Subscription, PaymentTransaction, User, Organization]


def request_for(user):
    request = RequestFactory().get("/admin/")
    request.user = user
    return request


def make_user(email: str, account_type: str, **extra) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type,
        is_staff=True, **extra
    )


@pytest.fixture
def content_admin(db) -> User:
    return make_user("moderation@bibliogabon.ga", User.AccountType.CONTENT_ADMIN)


@pytest.fixture
def super_admin(db) -> User:
    return User.objects.create_superuser(
        email="root@bibliogabon.ga", password="passphrase"
    )


@pytest.fixture
def staff_teacher(db) -> User:
    """Cas limite : un enseignant a qui on a donne is_staff par erreur.
    Il ne doit rien pouvoir faire de role-porteur pour autant."""
    return make_user("enseignant@bibliogabon.ga", User.AccountType.TEACHER_AUTHOR)


def permissions_for(model, user) -> dict[str, bool]:
    model_admin = admin.site._registry[model]
    request = request_for(user)
    return {
        "view": model_admin.has_view_permission(request),
        "add": model_admin.has_add_permission(request),
        "change": model_admin.has_change_permission(request),
        "delete": model_admin.has_delete_permission(request),
    }


@pytest.mark.django_db
@pytest.mark.parametrize("model", CONTENT_MODELS)
def test_a_content_admin_may_act_on_content(content_admin, model):
    assert all(permissions_for(model, content_admin).values()), model.__name__


@pytest.mark.django_db
@pytest.mark.parametrize("model", PLATFORM_MODELS)
def test_a_content_admin_is_refused_on_billing_and_platform_roles(content_admin, model):
    """Perimetre borne : moderer du contenu n'ouvre ni la facturation ni les
    roles plateforme."""
    assert not any(permissions_for(model, content_admin).values()), model.__name__


@pytest.mark.django_db
@pytest.mark.parametrize("model", CONTENT_MODELS + PLATFORM_MODELS)
def test_a_super_admin_may_act_on_everything(super_admin, model):
    assert all(permissions_for(model, super_admin).values()), model.__name__


@pytest.mark.django_db
@pytest.mark.parametrize("model", CONTENT_MODELS + PLATFORM_MODELS)
def test_a_staff_teacher_holds_no_administrative_authority(staff_teacher, model):
    assert not any(permissions_for(model, staff_teacher).values()), model.__name__


@pytest.mark.django_db
@pytest.mark.parametrize("model", CONTENT_MODELS + PLATFORM_MODELS)
def test_module_visibility_follows_the_same_rule(content_admin, staff_teacher, model):
    model_admin = admin.site._registry[model]

    expected = model in CONTENT_MODELS
    assert model_admin.has_module_permission(request_for(content_admin)) is expected
    assert model_admin.has_module_permission(request_for(staff_teacher)) is False


@pytest.mark.django_db
@pytest.mark.parametrize("actor", ["content_admin", "super_admin", "staff_teacher"])
def test_the_audit_log_stays_append_only_for_everyone(
    request, content_admin, super_admin, staff_teacher, actor
):
    """Y compris pour le super administrateur : une trace d'audit modifiable
    n'est plus une trace."""
    user = request.getfixturevalue(actor)
    model_admin = admin.site._registry[AuditLog]
    http_request = request_for(user)

    assert model_admin.has_add_permission(http_request) is False
    assert model_admin.has_change_permission(http_request) is False
    assert model_admin.has_delete_permission(http_request) is False


@pytest.mark.django_db
def test_a_superuser_with_a_drifted_account_type_is_not_locked_out(db):
    """Les surcharges has_*_permission court-circuitent le bypass superuser
    de Django : un compte racine mal typé serait enferme dehors."""
    root = User.objects.create_superuser(email="root2@bibliogabon.ga", password="p")
    root.account_type = User.AccountType.INDIVIDUAL
    root.save(update_fields=["account_type"])

    assert all(permissions_for(CommercialOffer, root).values())
