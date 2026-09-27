"""Retrait et archivage.

Les deux transitions existaient comme valeurs d'énumération sans service pour
les atteindre : `withdrawn_at` n'était jamais que remis à zéro. Les six états
retenus par D014 étaient donc, en pratique, quatre.

Le retrait n'est ni une suppression ni un effacement logique. La gouvernance est
explicite : « Withdrawal must be reversible internally. The public state
changes, but processing records, audit logs, contracts, and metadata history
remain available to authorized staff. » C'est ce que ces tests vérifient.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.utils import timezone

from catalog.models import Document, RightsAgreement
from document_ingestion.pipeline import ingest_document_file
from document_processing.models import DocumentPage
from document_reader.services import document_is_reader_accessible
from operations.models import AuditLog
from operations.services import archive_document, withdraw_document
from operations.tests.factories import create_publishable_document, create_user
from search_discovery.models import DocumentSearchIndex


@pytest.fixture
def moderator(db):
    return create_user(email="moderateur@bibliogabon.ga")


@pytest.fixture
def published(db):
    document = create_publishable_document(slug="document-retirable")
    document.publication_status = Document.PublicationStatus.PUBLISHED
    document.published_at = timezone.now()
    document.save(update_fields=["publication_status", "published_at", "updated_at"])
    return document


@pytest.mark.django_db
def test_withdrawing_a_published_document_changes_its_state_and_dates(published, moderator):
    withdrawn = withdraw_document(
        document=published, reason="Licence invalidée par l'éditeur.", actor=moderator
    )

    withdrawn.refresh_from_db()
    assert withdrawn.publication_status == Document.PublicationStatus.WITHDRAWN
    assert withdrawn.withdrawn_at is not None


@pytest.mark.django_db
def test_withdrawing_records_one_audit_event_naming_the_actor_and_the_reason(
    published, moderator
):
    """Un document public qui disparaît sans motif enregistré est précisément
    ce qu'un audit sert à empêcher."""
    before = AuditLog.objects.count()

    withdraw_document(
        document=published, reason="Licence invalidée par l'éditeur.", actor=moderator
    )

    assert AuditLog.objects.count() == before + 1
    event = AuditLog.objects.order_by("-created_at").first()
    assert event.event_type == "document_withdrawn"
    assert event.actor == moderator
    assert "Licence invalidée" in event.metadata["reason"]


@pytest.mark.django_db
def test_a_withdrawal_without_a_reason_is_refused(published, moderator):
    with pytest.raises(ValueError):
        withdraw_document(document=published, reason="   ", actor=moderator)

    published.refresh_from_db()
    assert published.publication_status == Document.PublicationStatus.PUBLISHED


@pytest.mark.django_db
def test_withdrawing_a_draft_is_refused(moderator):
    """Retirer ce qui n'a jamais paru n'a pas de sens : il n'y a rien à retirer
    du public, et l'état serait faux."""
    draft = create_publishable_document(slug="brouillon-non-retirable")

    with pytest.raises(ValueError):
        withdraw_document(document=draft, reason="Motif", actor=moderator)


@pytest.mark.django_db
def test_archiving_a_document_closes_it(published, moderator):
    archived = archive_document(
        document=published, reason="Fonds transféré aux Archives nationales.", actor=moderator
    )

    archived.refresh_from_db()
    assert archived.publication_status == Document.PublicationStatus.ARCHIVED
    event = AuditLog.objects.order_by("-created_at").first()
    assert event.event_type == "document_archived"
    assert event.actor == moderator


@pytest.mark.django_db
def test_archiving_twice_is_refused(published, moderator):
    archive_document(document=published, reason="Motif suffisant.", actor=moderator)

    with pytest.raises(ValueError):
        archive_document(document=published, reason="Motif suffisant.", actor=moderator)


@pytest.mark.django_db
def test_an_archived_document_can_still_be_withdrawn_from_nothing(moderator):
    """Un archivage est la fin de vie du document ; le retirer ensuite n'a pas
    de sens, puisqu'il n'est déjà plus lisible."""
    document = create_publishable_document(slug="document-archive")
    document.publication_status = Document.PublicationStatus.ARCHIVED
    document.save(update_fields=["publication_status", "updated_at"])

    with pytest.raises(ValueError):
        withdraw_document(document=document, reason="Motif", actor=moderator)


@pytest.mark.django_db
def test_a_withdrawal_without_an_actor_is_refused(published):
    """Un retrait anonyme est intraçable, ce qui vide l'audit de son sens."""
    with pytest.raises(ValueError):
        withdraw_document(document=published, reason="Motif suffisant.", actor=None)


@pytest.mark.django_db
def test_withdrawing_keeps_the_content_and_the_rights(published, moderator, tmp_path, settings):
    """Le retrait n'est ni une suppression ni une révocation de droits.

    Confondre retrait et révocation ferait exiger une nouvelle approbation des
    droits à une republication qui n'en a pas besoin.
    """
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    fixture = (
        Path(__file__).resolve().parents[2]
        / "document_ingestion"
        / "tests"
        / "fixtures"
        / "sample-3-pages.pdf"
    )
    with fixture.open("rb") as handle:
        version = ingest_document_file(
            document=published, fileobj=handle, original_filename="s.pdf"
        )
    pages_before = DocumentPage.objects.filter(version=version).count()
    index_before = DocumentSearchIndex.objects.filter(document=published).count()
    rights_before = RightsAgreement.objects.get(document=published).authorization_status

    withdraw_document(document=published, reason="Motif suffisant.", actor=moderator)

    assert DocumentPage.objects.filter(version=version).count() == pages_before
    assert DocumentSearchIndex.objects.filter(document=published).count() == index_before
    assert RightsAgreement.objects.get(document=published).authorization_status == rights_before
    version.refresh_from_db()
    assert version.page_count == pages_before


@pytest.mark.django_db
def test_a_withdrawn_document_is_not_readable(published, moderator):
    assert document_is_reader_accessible(published) is True

    withdraw_document(document=published, reason="Motif suffisant.", actor=moderator)

    published.refresh_from_db()
    assert document_is_reader_accessible(published) is False


@pytest.mark.django_db
def test_an_archived_document_is_not_readable(published, moderator):
    archive_document(document=published, reason="Motif suffisant.", actor=moderator)

    published.refresh_from_db()
    assert document_is_reader_accessible(published) is False


@pytest.mark.django_db
def test_republishing_a_withdrawn_document_clears_the_withdrawal_date(published, moderator):
    """La gouvernance exige qu'une republication passe par une nouvelle
    décision de validation. Elle doit alors effacer la date de retrait, sinon
    le document reste marqué comme retiré tout en étant lisible."""
    from operations.services import open_publication_review, record_publication_decision

    withdraw_document(document=published, reason="Motif suffisant.", actor=moderator)
    published.refresh_from_db()
    assert published.withdrawn_at is not None

    review = open_publication_review(document=published, actor=moderator)
    record_publication_decision(
        review=review,
        decision="approved",
        actor=moderator,
        reason="Licence à nouveau valide.",
    )

    published.refresh_from_db()
    assert published.publication_status == Document.PublicationStatus.PUBLISHED
    assert published.withdrawn_at is None
    assert document_is_reader_accessible(published) is True


@pytest.mark.django_db
def test_the_stored_reason_is_not_truncated_into_meaninglessness(published, moderator):
    """Le résumé d'audit est borné à 240 caractères ; le motif complet doit donc
    vivre dans `metadata`, où rien ne le coupe."""
    reason = "Motif détaillé. " * 40

    withdraw_document(document=published, reason=reason, actor=moderator)

    event = AuditLog.objects.order_by("-created_at").first()
    assert event.metadata["reason"] == reason.strip()
    assert len(event.summary) <= 240


@pytest.mark.django_db
def test_the_reader_surfaces_refuse_a_withdrawn_document(published, moderator, client):
    """Les deux surfaces de lecture partagent le même service ; le test le
    vérifie sur celle que le frontend utilise."""
    from django.urls import reverse

    withdraw_document(document=published, reason="Motif suffisant.", actor=moderator)

    response = client.post(
        reverse("api-v1:reader-session-create"),
        data={"document_id": published.pk},
        content_type="application/json",
    )
    assert response.status_code >= 400
