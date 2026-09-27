"""Signalement et demande de retrait, côté public.

Un back-office qui traite des signalements que personne ne peut déposer est
une décoration. Ces deux endpoints sont la seule entrée publique de la
tranche 4.
"""

from __future__ import annotations

import re

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import (
    AcademicDomain,
    Author,
    Document,
    DocumentAuthor,
    DocumentType,
)
from operations.models import SupportTicket


def make_user(email: str, account_type: str = User.AccountType.INDIVIDUAL) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type
    )


@pytest.fixture
def reader(db):
    return make_user("lecteur@example.ga")


@pytest.fixture
def author_user(db):
    return make_user("auteur@example.ga", User.AccountType.TEACHER_AUTHOR)


@pytest.fixture
def api():
    return APIClient()


def make_document(*, slug: str, author_user=None, status=Document.PublicationStatus.PUBLISHED):
    domain = AcademicDomain.objects.create(name=f"D {slug}", slug=f"d-{slug}")
    document_type = DocumentType.objects.create(name=f"T {slug}", slug=f"t-{slug}")
    document = Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=status,
        published_at=timezone.now() if status == Document.PublicationStatus.PUBLISHED else None,
    )
    if author_user is not None:
        author = Author.objects.create(display_name="Auteur", linked_user=author_user)
        DocumentAuthor.objects.create(
            document=document, author=author, role=DocumentAuthor.Role.AUTHOR, position=1
        )
    return document


def report_path(document):
    return reverse("api-v1:document-report", kwargs={"document_id": document.pk})


def request_path(document):
    return reverse("api-v1:document-withdrawal-request", kwargs={"document_id": document.pk})


# --- Signalement -----------------------------------------------------------


@pytest.mark.django_db
def test_a_reader_reports_a_published_document(api, reader):
    document = make_document(slug="signalable")
    api.force_authenticate(user=reader)

    response = api.post(
        report_path(document), {"reason": "Contient des données personnelles."}, format="json"
    )

    assert response.status_code == 201
    ticket = SupportTicket.objects.get()
    assert ticket.category == SupportTicket.Category.DOCUMENT_REPORT
    assert ticket.created_by == reader


@pytest.mark.django_db
def test_an_anonymous_visitor_cannot_report(api):
    """Un signalement anonyme n'est pas traçable, et le traiter demanderait de
    recontacter quelqu'un dont on ne sait rien."""
    document = make_document(slug="signalable-anonyme")

    response = api.post(report_path(document), {"reason": "Motif."}, format="json")

    assert response.status_code in {401, 403}
    assert SupportTicket.objects.count() == 0


@pytest.mark.django_db
def test_reporting_a_draft_returns_not_found_rather_than_forbidden(api, reader):
    """Répondre « interdit » confirmerait que le brouillon existe. C'est la
    même règle que sur le périmètre staff, et pour la même raison."""
    draft = make_document(slug="brouillon-signalable", status=Document.PublicationStatus.DRAFT)
    api.force_authenticate(user=reader)

    response = api.post(report_path(draft), {"reason": "Motif."}, format="json")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_a_report_without_a_reason_is_refused_on_the_field(api, reader):
    document = make_document(slug="signalable-sans-motif")
    api.force_authenticate(user=reader)

    response = api.post(report_path(document), {"reason": "  "}, format="json")

    assert response.status_code == 400
    assert "reason" in response.json()["error"]["field_errors"]


# --- Demande de retrait ----------------------------------------------------


@pytest.mark.django_db
def test_an_author_requests_withdrawal_of_their_own_deposit(api, author_user):
    document = make_document(slug="retrait-demande", author_user=author_user)
    api.force_authenticate(user=author_user)

    response = api.post(request_path(document), {"reason": "Version obsolète."}, format="json")

    assert response.status_code == 201
    assert SupportTicket.objects.get().category == SupportTicket.Category.WITHDRAWAL_REQUEST
    document.refresh_from_db()
    assert document.publication_status == Document.PublicationStatus.PUBLISHED


@pytest.mark.django_db
def test_a_reader_who_is_not_the_author_cannot_request_withdrawal(api, reader, author_user):
    """Le retrait appartient à l'auteur ou à la modération. Un lecteur gêné par
    un document le signale, ce qui est la voie prévue pour lui."""
    document = make_document(slug="retrait-non-auteur", author_user=author_user)
    api.force_authenticate(user=reader)

    response = api.post(request_path(document), {"reason": "Je n'aime pas."}, format="json")

    assert response.status_code == 403
    assert SupportTicket.objects.count() == 0


@pytest.mark.django_db
def test_a_content_admin_may_request_withdrawal_on_any_document(api, author_user):
    document = make_document(slug="retrait-moderateur", author_user=author_user)
    api.force_authenticate(user=make_user("mod@bibliogabon.ga", User.AccountType.CONTENT_ADMIN))

    response = api.post(request_path(document), {"reason": "Signalement fondé."}, format="json")

    assert response.status_code == 201


@pytest.mark.django_db
def test_the_response_never_carries_storage_details(api, author_user):
    document = make_document(slug="retrait-confidentialite", author_user=author_user)
    api.force_authenticate(user=author_user)

    body = api.post(
        request_path(document), {"reason": "Motif."}, format="json"
    ).content.decode()

    assert not re.search(r"\.pdf|://|storage|bucket", body, re.I)


@pytest.mark.django_db
def test_the_response_shape_is_the_ticket_not_the_document(api, author_user):
    document = make_document(slug="retrait-forme", author_user=author_user)
    api.force_authenticate(user=author_user)

    payload = api.post(request_path(document), {"reason": "Motif."}, format="json").json()

    assert set(payload) == {"id", "category", "status", "title", "opened_at"}
