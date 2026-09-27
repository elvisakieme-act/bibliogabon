"""Signalements et demandes de retrait.

`SupportTicket` n'avait pas de catégorie : un signalement et une demande de
retrait y étaient indistinguables d'une question de support. Une demande de
retrait appelle pourtant un **acte**, quand une question appelle une réponse,
et les mélanger fait dormir la première dans une file générique.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from catalog.models import Document
from operations.models import AuditLog, SupportTicket
from operations.services import (
    report_document,
    request_document_withdrawal,
    resolve_support_ticket,
)
from operations.tests.factories import create_publishable_document, create_user


@pytest.fixture
def reader(db):
    return create_user(email="lecteur-signalement@example.ga")


@pytest.fixture
def published(db):
    document = create_publishable_document(slug="document-signalable")
    document.publication_status = Document.PublicationStatus.PUBLISHED
    document.published_at = timezone.now()
    document.save(update_fields=["publication_status", "published_at", "updated_at"])
    return document


# --- Signalement -----------------------------------------------------------


@pytest.mark.django_db
def test_reporting_creates_a_categorised_ticket(published, reader):
    ticket = report_document(
        document=published,
        reason="Le document contient des données personnelles.",
        reported_by=reader,
    )

    assert ticket.category == SupportTicket.Category.DOCUMENT_REPORT
    assert ticket.document == published
    assert ticket.created_by == reader
    assert "données personnelles" in ticket.description


@pytest.mark.django_db
def test_reporting_writes_one_event_on_the_document_and_one_on_the_ticket(published, reader):
    """Deux cibles, deux faits : la trace du document dit qu'il a été signalé,
    celle du ticket dit qu'un ticket s'est ouvert. Les confondre priverait le
    journal du document de l'information qui l'intéresse."""
    report_document(document=published, reason="Contenu inapproprié.", reported_by=reader)

    on_document = AuditLog.objects.filter(
        target_app="catalog", target_model="document", target_id=str(published.pk)
    )
    assert [event.event_type for event in on_document] == ["document_reported"]
    assert on_document.first().actor == reader
    assert AuditLog.objects.filter(event_type="support_ticket_opened").count() == 1


@pytest.mark.django_db
def test_a_report_without_a_reason_is_refused(published, reader):
    with pytest.raises(ValueError):
        report_document(document=published, reason="   ", reported_by=reader)

    assert SupportTicket.objects.count() == 0


@pytest.mark.django_db
def test_an_anonymous_report_is_refused(published):
    """Un signalement anonyme n'est pas traçable, et le traiter demanderait de
    recontacter quelqu'un dont on ne sait rien."""
    with pytest.raises(ValueError):
        report_document(document=published, reason="Motif suffisant.", reported_by=None)


# --- Demande de retrait ----------------------------------------------------


@pytest.mark.django_db
def test_a_withdrawal_request_creates_a_ticket_and_withdraws_nothing(published, reader):
    """La demande n'est pas le retrait. Un auteur qui retirerait directement
    contournerait les règles contractuelles de `can_withdraw_document`."""
    ticket = request_document_withdrawal(
        document=published, reason="Version obsolète.", requested_by=reader
    )

    assert ticket.category == SupportTicket.Category.WITHDRAWAL_REQUEST
    published.refresh_from_db()
    assert published.publication_status == Document.PublicationStatus.PUBLISHED
    assert published.withdrawn_at is None


@pytest.mark.django_db
def test_a_withdrawal_request_on_a_draft_is_refused(reader):
    """Il n'y a rien à retirer d'un brouillon : accepter la demande
    promettrait un acte qui ne peut pas avoir lieu."""
    draft = create_publishable_document(slug="brouillon-non-demandable")

    with pytest.raises(ValueError):
        request_document_withdrawal(
            document=draft, reason="Motif suffisant.", requested_by=reader
        )


@pytest.mark.django_db
def test_a_withdrawal_request_without_a_reason_is_refused(published, reader):
    with pytest.raises(ValueError):
        request_document_withdrawal(document=published, reason="", requested_by=reader)


@pytest.mark.django_db
def test_a_withdrawal_request_is_prioritised_above_a_plain_question(published, reader):
    """Une demande de retrait peut porter sur des droits ou une
    confidentialité : elle ne doit pas attendre derrière une question de
    facturation."""
    ticket = request_document_withdrawal(
        document=published, reason="Consentement retiré.", requested_by=reader
    )

    assert ticket.priority == SupportTicket.Priority.HIGH


# --- Résolution ------------------------------------------------------------


@pytest.mark.django_db
def test_resolving_a_withdrawal_request_leaves_the_document_untouched(published, reader):
    """Résoudre est une réponse ; retirer est un acte. Le modérateur doit agir
    sur le document, et fermer le ticket ne le fait pas à sa place."""
    ticket = request_document_withdrawal(
        document=published, reason="Version obsolète.", requested_by=reader
    )

    resolve_support_ticket(
        ticket=ticket,
        actor=reader,
        resolution_summary="Demande examinée, retrait effectué à part.",
    )

    published.refresh_from_db()
    assert published.publication_status == Document.PublicationStatus.PUBLISHED


@pytest.mark.django_db
def test_an_existing_ticket_keeps_its_meaning(db, reader):
    """Le champ arrive avec une valeur par défaut : les tickets déjà en base
    restent des demandes de support, ce qu'ils étaient."""
    from operations.services import open_support_ticket

    ticket = open_support_ticket(
        title="Paiement refusé", description="Ma carte est rejetée.", created_by=reader
    )

    assert ticket.category == SupportTicket.Category.SUPPORT
