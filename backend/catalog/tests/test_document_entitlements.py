import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Entitlement
from accounts.services import user_has_entitlement
from catalog.models import AcademicDomain, Document


@pytest.mark.django_db
def test_document_entitlement_grants_access_to_matching_document_only():
    User = get_user_model()
    user = User.objects.create_user(email="reader@example.ga", password="pass")
    domain = AcademicDomain.objects.create(
        name="Sciences sociales",
        slug="sciences-sociales",
    )
    allowed = Document.objects.create(
        title="Sociologie gabonaise",
        slug="sociologie-gabonaise",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    denied = Document.objects.create(
        title="Anthropologie gabonaise",
        slug="anthropologie-gabonaise",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.ADMIN_GRANT,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=allowed.entitlement_scope_id,
        starts_at=timezone.now() - timezone.timedelta(hours=1),
        ends_at=timezone.now() + timezone.timedelta(hours=1),
    )

    assert (
        user_has_entitlement(
            user,
            Entitlement.AccessRight.READ,
            scope_type=Entitlement.ScopeType.DOCUMENT,
            scope_id=allowed.entitlement_scope_id,
        )
        is True
    )
    assert (
        user_has_entitlement(
            user,
            Entitlement.AccessRight.READ,
            scope_type=Entitlement.ScopeType.DOCUMENT,
            scope_id=denied.entitlement_scope_id,
        )
        is False
    )
