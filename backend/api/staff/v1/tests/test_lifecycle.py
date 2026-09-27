"""Retrait, archivage et journal d'audit.

Le journal était écrit fidèlement et illisible hors de Django Admin, qui en
montre le JSON brut. Une garantie de traçabilité que personne ne peut
consulter est une garantie sur le papier.
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
    RightsAgreement,
)
from operations.services import record_audit_event


def make_user(email: str, account_type: str) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type
    )


@pytest.fixture
def teacher(db):
    return make_user("enseignant-cycle@example.ga", User.AccountType.TEACHER_AUTHOR)


@pytest.fixture
def moderator(db):
    return make_user("moderateur-cycle@bibliogabon.ga", User.AccountType.CONTENT_ADMIN)


@pytest.fixture
def api():
    return APIClient()


def make_published(
    *, slug: str, author_user=None, category: str = Document.Category.VOLUNTARY_TEACHER_DEPOSIT
) -> Document:
    domain = AcademicDomain.objects.create(name=f"D {slug}", slug=f"d-{slug}")
    document_type = DocumentType.objects.create(name=f"T {slug}", slug=f"t-{slug}")
    document = Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        document_type=document_type,
        category=category,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    author = Author.objects.create(display_name="Auteur", linked_user=author_user)
    DocumentAuthor.objects.create(
        document=document, author=author, role=DocumentAuthor.Role.AUTHOR, position=1
    )
    RightsAgreement.objects.create(
        document=document,
        rights_holder_name="Titulaire",
        agreement_type=RightsAgreement.AgreementType.OPEN_LICENSE,
        authorization_status=RightsAgreement.AuthorizationStatus.APPROVED,
        authorization_date=timezone.now().date(),
        access_model=document.access_model,
        withdrawal_rule=RightsAgreement.WithdrawalRule.LICENSE_INVALID,
        reviewer_decision="Approuvé",
        audit_reference=f"audit-{slug}",
    )
    return document


def withdraw_path(document):
    return reverse("api-staff-v1:document-withdraw", kwargs={"document_id": document.pk})


def archive_path(document):
    return reverse("api-staff-v1:document-archive", kwargs={"document_id": document.pk})


def audit_path(document):
    return reverse("api-staff-v1:document-audit", kwargs={"document_id": document.pk})


# --- Retrait ---------------------------------------------------------------


@pytest.mark.django_db
def test_a_teacher_withdraws_their_own_voluntary_deposit(api, teacher):
    document = make_published(slug="retrait-volontaire", author_user=teacher)
    api.force_authenticate(user=teacher)

    response = api.post(withdraw_path(document), {"reason": "Version obsolète."}, format="json")

    assert response.status_code == 200
    document.refresh_from_db()
    assert document.publication_status == Document.PublicationStatus.WITHDRAWN


@pytest.mark.django_db
def test_a_teacher_is_refused_on_an_institutional_fund(api, teacher):
    """« Les fonds institutionnels suivent les règles du contrat. » Un retrait
    unilatéral y romprait un engagement."""
    document = make_published(
        slug="retrait-fonds",
        author_user=teacher,
        category=Document.Category.INSTITUTIONAL_FUND,
    )
    api.force_authenticate(user=teacher)

    response = api.post(withdraw_path(document), {"reason": "Je change d'avis."}, format="json")

    assert response.status_code == 403
    document.refresh_from_db()
    assert document.publication_status == Document.PublicationStatus.PUBLISHED


@pytest.mark.django_db
def test_a_content_admin_may_withdraw_an_institutional_fund(api, moderator, teacher):
    document = make_published(
        slug="retrait-fonds-moderateur",
        author_user=teacher,
        category=Document.Category.INSTITUTIONAL_FUND,
    )
    api.force_authenticate(user=moderator)

    response = api.post(withdraw_path(document), {"reason": "Contrat résilié."}, format="json")

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_teacher_is_refused_on_someone_elses_document(api, teacher, moderator):
    document = make_published(slug="retrait-autrui", author_user=moderator)
    api.force_authenticate(user=teacher)

    assert api.post(
        withdraw_path(document), {"reason": "Motif."}, format="json"
    ).status_code in {
        403,
        404,
    }


@pytest.mark.django_db
def test_a_withdrawal_without_a_reason_is_refused_on_the_right_field(api, moderator, teacher):
    document = make_published(slug="retrait-sans-motif", author_user=teacher)
    api.force_authenticate(user=moderator)

    response = api.post(withdraw_path(document), {"reason": "  "}, format="json")

    assert response.status_code == 400
    assert "reason" in response.json()["error"]["field_errors"]
    document.refresh_from_db()
    assert document.publication_status == Document.PublicationStatus.PUBLISHED


@pytest.mark.django_db
def test_withdrawing_a_draft_is_refused_as_a_conflict(api, moderator, teacher):
    document = make_published(slug="retrait-brouillon", author_user=teacher)
    document.publication_status = Document.PublicationStatus.DRAFT
    document.save(update_fields=["publication_status", "updated_at"])
    api.force_authenticate(user=moderator)

    response = api.post(withdraw_path(document), {"reason": "Motif."}, format="json")

    assert response.status_code == 409


# --- Archivage -------------------------------------------------------------


@pytest.mark.django_db
def test_a_content_admin_archives_a_document(api, moderator, teacher):
    document = make_published(slug="archivage", author_user=teacher)
    api.force_authenticate(user=moderator)

    response = api.post(
        archive_path(document), {"reason": "Transféré aux Archives nationales."}, format="json"
    )

    assert response.status_code == 200
    document.refresh_from_db()
    assert document.publication_status == Document.PublicationStatus.ARCHIVED


@pytest.mark.django_db
def test_a_teacher_cannot_archive_even_their_own_document(api, teacher):
    """L'archivage est la fin de vie du document sur la plateforme, pas un
    retrait réversible : il appartient à la modération."""
    document = make_published(slug="archivage-enseignant", author_user=teacher)
    api.force_authenticate(user=teacher)

    assert (
        api.post(archive_path(document), {"reason": "Motif."}, format="json").status_code == 403
    )


# --- Journal d'audit -------------------------------------------------------


@pytest.mark.django_db
def test_the_audit_trail_lists_events_newest_first(api, moderator, teacher):
    document = make_published(slug="audit-ordre", author_user=teacher)
    api.force_authenticate(user=moderator)
    api.post(withdraw_path(document), {"reason": "Premier motif."}, format="json")
    api.post(archive_path(document), {"reason": "Second motif."}, format="json")

    payload = api.get(audit_path(document)).json()

    types = [row["event_type"] for row in payload["results"]]
    assert types[:2] == ["document_archived", "document_withdrawn"]
    assert payload["results"][0]["actor"]["display_name"]
    assert payload["results"][0]["metadata"]["reason"] == "Second motif."


@pytest.mark.django_db
def test_a_teacher_is_refused_on_the_audit_trail(api, teacher):
    """Le journal nomme qui a fait quoi sur l'ensemble du catalogue ; il n'a
    rien à faire entre les mains d'un déposant."""
    document = make_published(slug="audit-refus", author_user=teacher)
    api.force_authenticate(user=teacher)

    assert api.get(audit_path(document)).status_code == 403


@pytest.mark.django_db
def test_the_audit_metadata_is_filtered_through_an_allow_list(api, moderator, teacher):
    """Une règle de confidentialité qui dépend de la prudence de chaque auteur
    futur n'est pas une règle.

    `metadata` est écrit par de nombreux services ; l'un d'eux pourrait un jour
    y placer une clé de stockage. L'événement ci-dessous en contient une
    délibérément.
    """
    document = make_published(slug="audit-empoisonne", author_user=teacher)
    record_audit_event(
        actor=moderator,
        event_type="document_source_uploaded",
        target=document,
        summary="Dépôt d'un fichier source",
        metadata={
            "document_id": document.pk,
            "reason": "Motif légitime.",
            "storage_key": "documents/42/versions/v1/source.pdf",
            "signed_url": "https://bucket.example.com/source.pdf?sig=abc",
        },
    )
    api.force_authenticate(user=moderator)

    body = api.get(audit_path(document)).content.decode()

    assert "Motif légitime." in body
    assert not re.search(r"\.pdf|://|storage|bucket", body, re.I)


@pytest.mark.django_db
def test_the_audit_trail_is_scoped_to_its_document(api, moderator, teacher):
    first = make_published(slug="audit-premier", author_user=teacher)
    second = make_published(slug="audit-second", author_user=teacher)
    api.force_authenticate(user=moderator)
    api.post(withdraw_path(first), {"reason": "Motif du premier."}, format="json")

    payload = api.get(audit_path(second)).json()

    assert all("premier" not in str(row).lower() for row in payload["results"])


@pytest.mark.django_db
def test_the_audit_trail_of_an_unknown_document_is_not_found(api, moderator):
    response = api.get(reverse("api-staff-v1:document-audit", kwargs={"document_id": 999999}))
    api.force_authenticate(user=moderator)

    assert response.status_code in {401, 403, 404}
