"""Organisations : membres, quotas et rapport d'usage.

Le risque produit de la tranche est ici. Un endpoint qui ferait confiance à un
filtre appliqué après coup, au lieu de passer l'organisation en argument au
prédicat, exposerait les membres d'une institution à une autre — et c'est le
genre de défaut qui survit à une suite de tests verte, parce que le cas
nominal marche parfaitement.

Chaque endpoint est donc éprouvé sur un accès croisé, pas seulement sur le
prédicat : les deux peuvent diverger.
"""

from __future__ import annotations

import re

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Organization, OrganizationMembership, User
from billing.models import CommercialOffer, OrganizationQuota
from catalog.models import AcademicDomain, Document
from document_reader.services import user_can_read_document
from operations.models import AuditLog


def make_user(email: str, account_type: str = User.AccountType.INDIVIDUAL) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type
    )


def make_org(slug: str) -> Organization:
    return Organization.objects.create(
        name=slug.upper(),
        slug=slug,
        organization_type=Organization.OrganizationType.UNIVERSITY,
    )


def make_admin(email: str, organization: Organization) -> User:
    user = make_user(email, User.AccountType.ORGANIZATION_ADMIN)
    OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=OrganizationMembership.Role.ADMIN,
        status=OrganizationMembership.Status.ACTIVE,
    )
    return user


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def pair(db):
    mine, other = make_org("uob-org"), make_org("ustm-org")
    return {
        "mine": mine,
        "other": other,
        "admin": make_admin("admin-org@example.ga", mine),
        "foreign_admin": make_admin("admin-autre@example.ga", other),
    }


def detail(organization):
    return reverse(
        "api-staff-v1:organization-detail", kwargs={"organization_id": organization.pk}
    )


def members(organization):
    return reverse(
        "api-staff-v1:organization-members", kwargs={"organization_id": organization.pk}
    )


def quotas(organization):
    return reverse(
        "api-staff-v1:organization-quotas", kwargs={"organization_id": organization.pk}
    )


def report(organization):
    return reverse(
        "api-staff-v1:organization-report", kwargs={"organization_id": organization.pk}
    )


# --- Cadrage ---------------------------------------------------------------


@pytest.mark.django_db
def test_an_admin_lists_only_the_organizations_they_administer(api, pair):
    api.force_authenticate(user=pair["admin"])

    payload = api.get(reverse("api-staff-v1:organization-list")).json()

    assert [row["slug"] for row in payload["results"]] == ["uob-org"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path_for", [detail, members, quotas, report], ids=["detail", "members", "quotas", "report"]
)
def test_every_endpoint_refuses_another_organization(api, pair, path_for):
    """Vérifié à l'endpoint, et pas seulement dans le prédicat : les deux
    peuvent diverger, et c'est l'endpoint qui répond."""
    api.force_authenticate(user=pair["admin"])

    assert api.get(path_for(pair["other"])).status_code == 404


@pytest.mark.django_db
def test_writing_on_another_organization_is_refused(api, pair):
    api.force_authenticate(user=pair["admin"])
    outsider = make_user("nouveau@example.ga")

    response = api.post(
        members(pair["other"]), {"email": outsider.email, "role": "member"}, format="json"
    )

    assert response.status_code == 404
    assert not OrganizationMembership.objects.filter(
        organization=pair["other"], user=outsider
    ).exists()


@pytest.mark.django_db
def test_a_teacher_is_refused_everywhere(api, pair):
    api.force_authenticate(
        user=make_user("prof-org@example.ga", User.AccountType.TEACHER_AUTHOR)
    )

    assert api.get(reverse("api-staff-v1:organization-list")).json()["results"] == []
    assert api.get(detail(pair["mine"])).status_code == 404


@pytest.mark.django_db
def test_platform_staff_sees_every_organization(api, pair):
    api.force_authenticate(
        user=make_user("staff@bibliogabon.ga", User.AccountType.PLATFORM_STAFF)
    )

    payload = api.get(reverse("api-staff-v1:organization-list")).json()

    assert {row["slug"] for row in payload["results"]} == {"uob-org", "ustm-org"}


# --- Membres ---------------------------------------------------------------


@pytest.mark.django_db
def test_the_member_list_carries_the_verification_status(api, pair):
    """Une adhésion non vérifiée n'accorde rien. Un administrateur qui ne le
    voit pas ne comprendra pas pourquoi un membre ne peut pas lire."""
    member = make_user("membre@example.ga")
    OrganizationMembership.objects.create(
        organization=pair["mine"],
        user=member,
        role=OrganizationMembership.Role.MEMBER,
        status=OrganizationMembership.Status.ACTIVE,
        verification_status=OrganizationMembership.VerificationStatus.UNVERIFIED,
    )
    api.force_authenticate(user=pair["admin"])

    rows = api.get(members(pair["mine"])).json()["results"]

    row = next(r for r in rows if r["user"]["email"] == "membre@example.ga")
    assert row["verification_status"] == "unverified"


@pytest.mark.django_db
def test_adding_a_member_goes_through_the_audited_service(api, pair):
    outsider = make_user("recrue@example.ga")
    before = AuditLog.objects.count()
    api.force_authenticate(user=pair["admin"])

    response = api.post(
        members(pair["mine"]), {"email": outsider.email, "role": "member"}, format="json"
    )

    assert response.status_code == 201
    assert AuditLog.objects.count() == before + 1
    assert AuditLog.objects.order_by("-created_at").first().event_type == (
        "organization_member_added"
    )


@pytest.mark.django_db
def test_adding_an_unknown_email_is_refused_on_the_field(api, pair):
    api.force_authenticate(user=pair["admin"])

    response = api.post(
        members(pair["mine"]), {"email": "inconnu@example.ga", "role": "member"}, format="json"
    )

    assert response.status_code == 400
    assert "email" in response.json()["error"]["field_errors"]


@pytest.mark.django_db
def test_suspending_removes_reading_access_immediately(api, pair):
    """Le test vaut plus que le changement de champ : c'est l'accès qui doit
    tomber, et il dépend d'une adhésion active."""
    from accounts.models import Entitlement

    member = make_user("suspendable@example.ga")
    membership = OrganizationMembership.objects.create(
        organization=pair["mine"],
        user=member,
        role=OrganizationMembership.Role.MEMBER,
        status=OrganizationMembership.Status.ACTIVE,
    )
    Entitlement.objects.create(
        organization=pair["mine"],
        source=Entitlement.Source.ORGANIZATION_QUOTA,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=timezone.now() - timezone.timedelta(days=1),
    )
    domain = AcademicDomain.objects.create(name="Droit", slug="droit-suspension")
    document = Document.objects.create(
        title="Document restreint",
        slug="document-restreint-suspension",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.SUBSCRIPTION,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )
    assert user_can_read_document(member, document) is True

    api.force_authenticate(user=pair["admin"])
    response = api.post(
        reverse(
            "api-staff-v1:organization-member-suspend",
            kwargs={"organization_id": pair["mine"].pk, "membership_id": membership.pk},
        ),
        {"reason": "Départ temporaire."},
        format="json",
    )

    assert response.status_code == 200
    assert user_can_read_document(member, document) is False


@pytest.mark.django_db
def test_ending_a_membership_leaves_the_account_usable(api, pair):
    """Le retrait d'une organisation arrête l'accès qu'elle accordait ; il ne
    supprime ni l'utilisateur, ni son historique."""
    member = make_user("partant@example.ga")
    membership = OrganizationMembership.objects.create(
        organization=pair["mine"], user=member, status=OrganizationMembership.Status.ACTIVE
    )
    api.force_authenticate(user=pair["admin"])

    api.post(
        reverse(
            "api-staff-v1:organization-member-end",
            kwargs={"organization_id": pair["mine"].pk, "membership_id": membership.pk},
        ),
        {"reason": "Fin de contrat."},
        format="json",
    )

    member.refresh_from_db()
    membership.refresh_from_db()
    assert member.is_active is True
    assert membership.status == OrganizationMembership.Status.ENDED


@pytest.mark.django_db
def test_acting_on_a_membership_of_another_organization_is_refused(api, pair):
    member = make_user("membre-autre@example.ga")
    membership = OrganizationMembership.objects.create(
        organization=pair["other"], user=member, status=OrganizationMembership.Status.ACTIVE
    )
    api.force_authenticate(user=pair["admin"])

    response = api.post(
        reverse(
            "api-staff-v1:organization-member-suspend",
            kwargs={"organization_id": pair["mine"].pk, "membership_id": membership.pk},
        ),
        {"reason": "Tentative."},
        format="json",
    )

    assert response.status_code == 404
    membership.refresh_from_db()
    assert membership.status == OrganizationMembership.Status.ACTIVE


# --- Quotas ----------------------------------------------------------------


@pytest.mark.django_db
def test_the_quota_list_carries_seats_and_contract_reference(api, pair):
    offer = CommercialOffer.objects.create(
        name="Offre institutionnelle",
        slug="offre-institutionnelle",
        offer_type=CommercialOffer.OfferType.ORGANIZATION,
        billing_period=CommercialOffer.BillingPeriod.ANNUAL,
        price_xaf=500000,
        duration_days=365,
        access_right="read",
        scope_type="global",
    )
    OrganizationQuota.objects.create(
        organization=pair["mine"],
        offer=offer,
        seat_limit=250,
        starts_at=timezone.now(),
        ends_at=timezone.now() + timezone.timedelta(days=365),
        contract_reference="CONTRAT-UOB-2026",
    )
    api.force_authenticate(user=pair["admin"])

    rows = api.get(quotas(pair["mine"])).json()["results"]

    assert rows[0]["seat_limit"] == 250
    assert rows[0]["contract_reference"] == "CONTRAT-UOB-2026"


# --- Rapport d'usage --------------------------------------------------------


@pytest.mark.django_db
def test_the_usage_report_returns_aggregated_metrics(api, pair):
    api.force_authenticate(user=pair["admin"])

    payload = api.get(report(pair["mine"]), {"from": "2026-09-01", "to": "2026-09-30"}).json()

    assert set(payload["metrics"]) == {"access", "commercial", "support", "usage"}
    assert payload["period"] == {"start": "2026-09-01", "end": "2026-09-30"}


# Clés qui désigneraient une personne. La liste est **exacte** et non une
# recherche de sous-chaîne : `reader_session_count` est un agrégat légitime, et
# un test qui le rejetterait pousserait à affaiblir la règle plutôt qu'à la
# tenir.
PER_USER_KEYS = frozenset(
    {
        "user",
        "user_id",
        "user_email",
        "users",
        "reader_id",
        "readers",
        "client_ip",
        "session_key",
        "last_seen_at",
        "accessed_at",
        "page_access_logs",
    }
)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def walk_keys(value, path=""):
    """Toutes les clés du rapport, à toute profondeur."""
    if isinstance(value, dict):
        for key, nested in value.items():
            yield f"{path}.{key}" if path else key, key, nested
            yield from walk_keys(nested, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from walk_keys(nested, f"{path}[{index}]")


@pytest.mark.django_db
def test_the_usage_report_names_no_reader(api, pair):
    """Un rapport qui dirait qui a lu quoi transformerait une bibliothèque en
    outil de surveillance. Si une métrique future ajoute un champ par
    utilisateur, ce test échoue plutôt que la fuite ne parte en production.
    """
    api.force_authenticate(user=pair["admin"])

    response = api.get(report(pair["mine"]), {"from": "2026-09-01", "to": "2026-09-30"})
    payload = response.json()

    offending = [full for full, key, _ in walk_keys(payload["metrics"]) if key in PER_USER_KEYS]
    assert offending == [], offending
    assert not EMAIL.search(response.content.decode())


@pytest.mark.django_db
def test_an_invalid_period_is_refused_on_the_field(api, pair):
    api.force_authenticate(user=pair["admin"])

    response = api.get(report(pair["mine"]), {"from": "2026-09-30", "to": "2026-09-01"})

    assert response.status_code == 400
    assert response.json()["error"]["field_errors"]


@pytest.mark.django_db
def test_no_organization_payload_names_a_stored_object(api, pair):
    api.force_authenticate(user=pair["admin"])

    for path in (
        reverse("api-staff-v1:organization-list"),
        detail(pair["mine"]),
        members(pair["mine"]),
        quotas(pair["mine"]),
    ):
        body = api.get(path).content.decode()
        assert not re.search(r"\.pdf|://|storage|bucket", body, re.I), path


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action", "event_type"),
    [
        ("suspend", "organization_member_suspended"),
        ("end", "organization_member_ended"),
    ],
)
def test_membership_changes_go_through_the_audited_service(api, pair, action, event_type):
    """Écrire le champ directement produirait le même état visible et
    perdrait la trace. La chute d'accès ne suffit donc pas à le prouver :
    c'est l'événement qu'il faut vérifier.
    """
    member = make_user(f"audite-{action}@example.ga")
    membership = OrganizationMembership.objects.create(
        organization=pair["mine"], user=member, status=OrganizationMembership.Status.ACTIVE
    )
    before = AuditLog.objects.count()
    api.force_authenticate(user=pair["admin"])

    api.post(
        reverse(
            f"api-staff-v1:organization-member-{action}",
            kwargs={"organization_id": pair["mine"].pk, "membership_id": membership.pk},
        ),
        {"reason": "Motif consigné."},
        format="json",
    )

    assert AuditLog.objects.count() == before + 1
    event = AuditLog.objects.order_by("-created_at").first()
    assert event.event_type == event_type
    assert event.actor == pair["admin"]
    assert event.metadata["reason"] == "Motif consigné."
