from __future__ import annotations

import pytest
from django.urls import path
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from accounts.models import Organization, OrganizationMembership, User
from api.v1.permissions import AdministersOrganization, IsContentAdmin, IsTeacherOrContentAdmin


class ProbeView(APIView):
    """Vue jetable : on teste les classes de permission, pas un endpoint."""

    permission_classes = [IsContentAdmin]

    def get(self, request):
        return Response({"ok": True})


class TeacherProbeView(ProbeView):
    permission_classes = [IsTeacherOrContentAdmin]


class OrganizationProbeView(APIView):
    permission_classes = [AdministersOrganization]

    def get(self, request, organization_id: int):
        self.check_object_permissions(request, Organization.objects.get(pk=organization_id))
        return Response({"ok": True})


urlpatterns = [
    path("probe/content/", ProbeView.as_view()),
    path("probe/teacher/", TeacherProbeView.as_view()),
    path("probe/org/<int:organization_id>/", OrganizationProbeView.as_view()),
]


def make_user(email: str, account_type: str) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type
    )


@pytest.fixture
def api(settings):
    settings.ROOT_URLCONF = __name__
    return APIClient()


@pytest.mark.django_db
def test_anonymous_gets_401_not_403(api):
    """Un anonyme n'est pas « interdit » mais « non identifie » : la
    distinction compte pour un client qui doit savoir s'il faut se connecter."""
    response = api.get("/probe/content/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("account_type", "allowed"),
    [
        (User.AccountType.INDIVIDUAL, False),
        (User.AccountType.TEACHER_AUTHOR, False),
        (User.AccountType.ORGANIZATION_ADMIN, False),
        (User.AccountType.CONTENT_ADMIN, True),
        (User.AccountType.PLATFORM_STAFF, True),
    ],
)
def test_is_content_admin_refuses_every_other_actor(api, account_type, allowed):
    api.force_authenticate(make_user(f"{account_type}@example.ga", account_type))

    response = api.get("/probe/content/")

    assert response.status_code == (200 if allowed else 403)
    if not allowed:
        assert response.json()["error"]["code"] == "permission_denied"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("account_type", "allowed"),
    [
        (User.AccountType.INDIVIDUAL, False),
        (User.AccountType.TEACHER_AUTHOR, True),
        (User.AccountType.ORGANIZATION_ADMIN, False),
        (User.AccountType.CONTENT_ADMIN, True),
        (User.AccountType.PLATFORM_STAFF, True),
    ],
)
def test_is_teacher_or_content_admin(api, account_type, allowed):
    api.force_authenticate(make_user(f"t-{account_type}@example.ga", account_type))

    response = api.get("/probe/teacher/")

    assert response.status_code == (200 if allowed else 403)


@pytest.mark.django_db
def test_administers_organization_is_scoped_to_the_right_organization(api):
    uob = Organization.objects.create(name="UOB", slug="uob")
    ustm = Organization.objects.create(name="USTM", slug="ustm")
    admin = make_user("admin@uob.ga", User.AccountType.ORGANIZATION_ADMIN)
    OrganizationMembership.objects.create(
        organization=uob,
        user=admin,
        role=OrganizationMembership.Role.ADMIN,
        status=OrganizationMembership.Status.ACTIVE,
    )
    api.force_authenticate(admin)

    assert api.get(f"/probe/org/{uob.pk}/").status_code == 200
    refused = api.get(f"/probe/org/{ustm.pk}/")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "permission_denied"


@pytest.mark.django_db
def test_a_refusal_uses_the_standard_error_envelope(api):
    api.force_authenticate(make_user("etudiant@example.ga", User.AccountType.INDIVIDUAL))

    payload = api.get("/probe/content/").json()

    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"code", "message", "field_errors"}
