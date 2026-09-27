from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import (
    AcademicDomain, Author, Document, DocumentAuthor, DocumentType, RightsAgreement,
)
from operations.models import AuditLog


def make_user(email: str, account_type: str) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type
    )


@pytest.fixture
def reference(db):
    return {
        "domain": AcademicDomain.objects.create(name="Droit", slug="droit"),
        "type": DocumentType.objects.create(name="Cours", slug="cours"),
    }


@pytest.fixture
def teacher(db):
    return make_user("enseignant@example.ga", User.AccountType.TEACHER_AUTHOR)


@pytest.fixture
def moderator(db):
    return make_user("mod@bibliogabon.ga", User.AccountType.CONTENT_ADMIN)


@pytest.fixture
def api():
    return APIClient()


def create_payload(reference, **overrides):
    payload = {
        "title": "Introduction au droit public",
        "slug": "intro-droit-public",
        "abstract": "Un résumé.",
        "academic_domain": reference["domain"].pk,
        "document_type": reference["type"].pk,
        "category": Document.Category.VOLUNTARY_TEACHER_DEPOSIT,
        "access_model": Document.AccessModel.FREE,
    }
    payload.update(overrides)
    return payload


LIST = "api-staff-v1:document-list"
DETAIL = "api-staff-v1:document-detail"
SUBMIT = "api-staff-v1:document-submit"


# --- Création ----------------------------------------------------------------


def test_a_teacher_creates_a_draft_and_is_its_author(api, teacher, reference):
    api.force_authenticate(teacher)

    response = api.post(reverse(LIST), create_payload(reference), format="json")

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["publication_status"] == Document.PublicationStatus.DRAFT
    assert [a["display_name"] for a in body["authors"]] == [teacher.display_name or teacher.email]
    document = Document.objects.get(slug="intro-droit-public")
    assert document.document_authors.filter(author__linked_user=teacher).exists()


def test_the_payload_never_exposes_a_storage_key(api, teacher, reference):
    api.force_authenticate(teacher)

    body = api.post(reverse(LIST), create_payload(reference), format="json").content.decode()

    assert "storage" not in body.lower()
    assert "://" not in body


def test_the_payload_reports_rights_and_ingestion_state(api, teacher, reference):
    api.force_authenticate(teacher)

    body = api.post(reverse(LIST), create_payload(reference), format="json").json()

    assert body["rights"] is None
    assert body["ingestion"] is None
    # L'enseignant est rattaché comme auteur à la création : seul l'accord
    # de droits manque encore.
    assert body["missing_for_publication"] == ["rights_agreement"]


def test_a_student_cannot_create(api, reference):
    api.force_authenticate(make_user("etudiant@example.ga", User.AccountType.INDIVIDUAL))

    response = api.post(reverse(LIST), create_payload(reference), format="json")

    assert response.status_code == 403


# --- Lecture et filtres ------------------------------------------------------


def make_document(reference, *, slug, status, author=None):
    document = Document.objects.create(
        title=slug, slug=slug,
        academic_domain=reference["domain"], document_type=reference["type"],
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE, publication_status=status,
    )
    if author is not None:
        entry = Author.objects.create(
            display_name=author.email, normalized_name=author.email, linked_user=author
        )
        DocumentAuthor.objects.create(
            document=document, author=entry, role=DocumentAuthor.Role.AUTHOR
        )
    return document


def test_the_list_is_paginated_with_the_standard_envelope(api, moderator, reference):
    make_document(reference, slug="a", status=Document.PublicationStatus.DRAFT)
    api.force_authenticate(moderator)

    body = api.get(reverse(LIST)).json()

    assert set(body) == {"count", "next", "previous", "results"}


def test_filters_narrow_the_list(api, moderator, reference):
    make_document(reference, slug="brouillon", status=Document.PublicationStatus.DRAFT)
    make_document(reference, slug="publie", status=Document.PublicationStatus.PUBLISHED)
    api.force_authenticate(moderator)

    filtered = api.get(reverse(LIST), {"status": Document.PublicationStatus.DRAFT}).json()
    assert [d["slug"] for d in filtered["results"]] == ["brouillon"]

    by_domain = api.get(reverse(LIST), {"domain": "droit"}).json()
    assert by_domain["count"] == 2

    by_type = api.get(reverse(LIST), {"type": "cours"}).json()
    assert by_type["count"] == 2


def test_a_teacher_only_lists_their_own(api, teacher, reference):
    make_document(reference, slug="a-moi", status=Document.PublicationStatus.DRAFT, author=teacher)
    make_document(reference, slug="dautrui", status=Document.PublicationStatus.DRAFT)
    api.force_authenticate(teacher)

    body = api.get(reverse(LIST)).json()

    assert [d["slug"] for d in body["results"]] == ["a-moi"]


def test_a_teacher_gets_404_on_a_document_they_did_not_author(api, teacher, reference):
    """404 plutôt que 403 : répondre « interdit » révélerait que le document
    existe."""
    other = make_document(reference, slug="dautrui", status=Document.PublicationStatus.DRAFT)
    api.force_authenticate(teacher)

    assert api.get(reverse(DETAIL, args=[other.pk])).status_code == 404


# --- Modification ------------------------------------------------------------


def test_a_teacher_patches_their_own_document(api, teacher, reference):
    mine = make_document(reference, slug="a-moi", status=Document.PublicationStatus.DRAFT, author=teacher)
    api.force_authenticate(teacher)

    response = api.patch(reverse(DETAIL, args=[mine.pk]), {"abstract": "Corrigé."}, format="json")

    assert response.status_code == 200
    mine.refresh_from_db()
    assert mine.abstract == "Corrigé."


def test_a_teacher_cannot_patch_someone_elses_document(api, teacher, reference):
    other = make_document(reference, slug="dautrui", status=Document.PublicationStatus.DRAFT)
    api.force_authenticate(teacher)

    response = api.patch(reverse(DETAIL, args=[other.pk]), {"abstract": "x"}, format="json")

    assert response.status_code == 404
    other.refresh_from_db()
    assert other.abstract == ""


def test_a_moderator_can_patch_any_document(api, moderator, reference):
    other = make_document(reference, slug="dautrui", status=Document.PublicationStatus.DRAFT)
    api.force_authenticate(moderator)

    assert api.patch(
        reverse(DETAIL, args=[other.pk]), {"abstract": "Revu."}, format="json"
    ).status_code == 200


def test_the_publication_status_cannot_be_changed_by_patch(api, moderator, reference):
    """L'état de publication n'avance que par les transitions dédiées, qui
    sont auditées. Le laisser modifiable ici contournerait le workflow."""
    document = make_document(reference, slug="a", status=Document.PublicationStatus.DRAFT)
    api.force_authenticate(moderator)

    api.patch(
        reverse(DETAIL, args=[document.pk]),
        {"publication_status": Document.PublicationStatus.PUBLISHED},
        format="json",
    )

    document.refresh_from_db()
    assert document.publication_status == Document.PublicationStatus.DRAFT


# --- Soumission --------------------------------------------------------------


def complete(document, author_user):
    entry = Author.objects.create(
        display_name=author_user.email, normalized_name=author_user.email,
        linked_user=author_user,
    )
    DocumentAuthor.objects.create(
        document=document, author=entry, role=DocumentAuthor.Role.AUTHOR
    )
    from django.utils import timezone

    RightsAgreement.objects.create(
        document=document,
        agreement_type=RightsAgreement.AgreementType.TEACHER_VOLUNTARY,
        rights_holder_name="Auteur",
        authorization_status=RightsAgreement.AuthorizationStatus.APPROVED,
        authorization_date=timezone.now().date(),
        access_model=document.access_model,
        withdrawal_rule=RightsAgreement.WithdrawalRule.AUTHOR_REQUEST,
        reviewer_decision="Approuvé",
        audit_reference="BG-TEST-1",
    )
    return document


def test_submitting_moves_a_draft_to_submitted_and_audits_it(api, teacher, reference):
    document = complete(
        make_document(reference, slug="a-moi", status=Document.PublicationStatus.DRAFT),
        teacher,
    )
    api.force_authenticate(teacher)

    response = api.post(reverse(SUBMIT, args=[document.pk]))

    assert response.status_code == 200, response.json()
    document.refresh_from_db()
    assert document.publication_status == Document.PublicationStatus.SUBMITTED
    event = AuditLog.objects.order_by("-id").first()
    assert event.event_type == "document_submitted"
    assert event.actor_id == teacher.pk


def test_submitting_twice_is_idempotent(api, teacher, reference):
    document = complete(
        make_document(reference, slug="a-moi", status=Document.PublicationStatus.DRAFT),
        teacher,
    )
    api.force_authenticate(teacher)
    api.post(reverse(SUBMIT, args=[document.pk]))
    count = AuditLog.objects.count()

    response = api.post(reverse(SUBMIT, args=[document.pk]))

    assert response.status_code == 200
    assert AuditLog.objects.count() == count, "un non-changement ne s'audite pas"


def test_submitting_without_author_or_rights_names_what_is_missing(api, teacher, reference):
    document = make_document(reference, slug="incomplet", status=Document.PublicationStatus.DRAFT)
    entry = Author.objects.create(
        display_name=teacher.email, normalized_name=teacher.email, linked_user=teacher
    )
    DocumentAuthor.objects.create(
        document=document, author=entry, role=DocumentAuthor.Role.AUTHOR
    )
    api.force_authenticate(teacher)

    response = api.post(reverse(SUBMIT, args=[document.pk]))

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "incomplete_document"
    assert error["field_errors"]["missing"] == ["rights_agreement"]
