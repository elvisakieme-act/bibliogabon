"""File de support, signalements et demandes de retrait.

Le point sensible est le cadrage : un administrateur d'organisation ne doit
voir que les tickets de la sienne, et le refus doit être vérifié **à
l'endpoint**, pas seulement dans le prédicat. Les deux peuvent diverger.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Organization, OrganizationMembership, User
from catalog.models import AcademicDomain, Document, DocumentType
from operations.models import AuditLog, SupportTicket
from operations.services import open_support_ticket, report_document


def make_user(email: str, account_type: str) -> User:
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
def moderator(db):
    return make_user("mod-tickets@bibliogabon.ga", User.AccountType.CONTENT_ADMIN)


@pytest.fixture
def teacher(db):
    return make_user("prof-tickets@example.ga", User.AccountType.TEACHER_AUTHOR)


@pytest.fixture
def reader(db):
    return make_user("lecteur-tickets@example.ga", User.AccountType.INDIVIDUAL)


def make_published(slug: str, organization=None) -> Document:
    domain = AcademicDomain.objects.create(name=f"D {slug}", slug=f"d-{slug}")
    document_type = DocumentType.objects.create(name=f"T {slug}", slug=f"t-{slug}")
    return Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
        published_at=timezone.now(),
        owner_organization=organization,
    )


LIST = "api-staff-v1:ticket-list"


# --- Qui voit quoi ---------------------------------------------------------


@pytest.mark.django_db
def test_a_content_admin_sees_every_ticket(api, moderator, reader):
    report_document(document=make_published("t-un"), reason="Motif.", reported_by=reader)
    open_support_ticket(title="Paiement", description="Carte refusée.", created_by=reader)
    api.force_authenticate(user=moderator)

    payload = api.get(reverse(LIST)).json()

    assert payload["count"] == 2


@pytest.mark.django_db
def test_an_organization_admin_sees_only_their_own_organizations_tickets(api, reader):
    """Le cadrage est le point sensible de cette tranche : un filtre appliqué
    après coup exposerait les tickets d'une institution à une autre."""
    mine, other = make_org("uob-tickets"), make_org("ustm-tickets")
    admin = make_admin("admin-uob@example.ga", mine)
    report_document(
        document=make_published("t-a-moi", mine), reason="Motif.", reported_by=reader
    )
    report_document(
        document=make_published("t-a-autrui", other), reason="Motif.", reported_by=reader
    )
    open_support_ticket(title="Sans organisation", description="…", created_by=reader)
    api.force_authenticate(user=admin)

    payload = api.get(reverse(LIST)).json()

    slugs = {row["document"]["slug"] for row in payload["results"] if row["document"]}
    assert slugs == {"t-a-moi"}


@pytest.mark.django_db
def test_a_teacher_is_refused_on_the_queue(api, teacher):
    api.force_authenticate(user=teacher)

    assert api.get(reverse(LIST)).status_code == 403


@pytest.mark.django_db
def test_an_anonymous_visitor_is_refused(api):
    assert api.get(reverse(LIST)).status_code in {401, 403}


@pytest.mark.django_db
def test_an_organization_admin_is_refused_on_another_organizations_ticket(api, reader):
    mine, other = make_org("uob-detail"), make_org("ustm-detail")
    admin = make_admin("admin-detail@example.ga", mine)
    foreign = report_document(
        document=make_published("t-etranger", other), reason="Motif.", reported_by=reader
    )
    api.force_authenticate(user=admin)

    response = api.get(reverse("api-staff-v1:ticket-detail", kwargs={"ticket_id": foreign.pk}))

    # Introuvable plutôt qu'interdit : confirmer l'existence d'un ticket d'une
    # autre institution est déjà une fuite.
    assert response.status_code == 404


# --- Filtres ----------------------------------------------------------------


@pytest.mark.django_db
def test_the_queue_filters_by_category_and_status(api, moderator, reader):
    report_document(document=make_published("t-signale"), reason="Motif.", reported_by=reader)
    open_support_ticket(title="Question", description="…", created_by=reader)
    api.force_authenticate(user=moderator)

    reports = api.get(reverse(LIST), {"category": "document_report"}).json()
    assert [row["category"] for row in reports["results"]] == ["document_report"]

    resolved = api.get(reverse(LIST), {"status": "resolved"}).json()
    assert resolved["results"] == []


# --- Attribution et résolution ---------------------------------------------


@pytest.mark.django_db
def test_assigning_records_the_assignee(api, moderator, reader):
    ticket = open_support_ticket(title="Question", description="…", created_by=reader)
    api.force_authenticate(user=moderator)

    response = api.post(
        reverse("api-staff-v1:ticket-assign", kwargs={"ticket_id": ticket.pk}),
        {},
        format="json",
    )

    assert response.status_code == 200
    ticket.refresh_from_db()
    assert ticket.assigned_to == moderator


@pytest.mark.django_db
def test_resolving_requires_a_summary_on_the_right_field(api, moderator, reader):
    ticket = open_support_ticket(title="Question", description="…", created_by=reader)
    api.force_authenticate(user=moderator)

    response = api.post(
        reverse("api-staff-v1:ticket-resolve", kwargs={"ticket_id": ticket.pk}),
        {"resolution_summary": "  "},
        format="json",
    )

    assert response.status_code == 400
    assert "resolution_summary" in response.json()["error"]["field_errors"]
    ticket.refresh_from_db()
    assert ticket.status == SupportTicket.Status.OPEN


@pytest.mark.django_db
def test_resolving_writes_an_audit_event(api, moderator, reader):
    ticket = open_support_ticket(title="Question", description="…", created_by=reader)
    before = AuditLog.objects.count()
    api.force_authenticate(user=moderator)

    api.post(
        reverse("api-staff-v1:ticket-resolve", kwargs={"ticket_id": ticket.pk}),
        {"resolution_summary": "Réponse envoyée par téléphone."},
        format="json",
    )

    assert AuditLog.objects.count() == before + 1
    event = AuditLog.objects.order_by("-created_at").first()
    assert event.event_type == "support_ticket_resolved"
    assert event.actor == moderator


@pytest.mark.django_db
def test_resolving_twice_is_refused(api, moderator, reader):
    ticket = open_support_ticket(title="Question", description="…", created_by=reader)
    api.force_authenticate(user=moderator)
    path = reverse("api-staff-v1:ticket-resolve", kwargs={"ticket_id": ticket.pk})
    api.post(path, {"resolution_summary": "Traité."}, format="json")

    assert api.post(path, {"resolution_summary": "Encore."}, format="json").status_code == 409


@pytest.mark.django_db
def test_resolving_a_withdrawal_request_does_not_touch_the_document(api, moderator, reader):
    """Résoudre est une réponse ; retirer est un acte. Le modérateur doit agir
    sur le document, et fermer le ticket ne le fait pas à sa place."""
    from operations.services import request_document_withdrawal

    document = make_published("t-demande-retrait")
    ticket = request_document_withdrawal(
        document=document, reason="Version obsolète.", requested_by=reader
    )
    api.force_authenticate(user=moderator)

    api.post(
        reverse("api-staff-v1:ticket-resolve", kwargs={"ticket_id": ticket.pk}),
        {"resolution_summary": "Demande examinée."},
        format="json",
    )

    document.refresh_from_db()
    assert document.publication_status == Document.PublicationStatus.PUBLISHED


@pytest.mark.django_db
def test_no_ticket_payload_names_a_stored_object(api, moderator, reader):
    import re

    ticket = report_document(
        document=make_published("t-confidentialite"), reason="Motif.", reported_by=reader
    )
    api.force_authenticate(user=moderator)

    for path in (
        reverse(LIST),
        reverse("api-staff-v1:ticket-detail", kwargs={"ticket_id": ticket.pk}),
    ):
        body = api.get(path).content.decode()
        assert not re.search(r"\.pdf|://|storage|bucket", body, re.I), path
