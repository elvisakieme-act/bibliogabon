from __future__ import annotations

import pytest
from django.urls import reverse
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
from operations.models import AuditLog

AUTHORS = "api-staff-v1:document-authors"
AUTHOR_DETAIL = "api-staff-v1:document-author-detail"
RIGHTS = "api-staff-v1:document-rights"
DECISION = "api-staff-v1:document-rights-decision"


def make_user(email: str, account_type: str) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type
    )


@pytest.fixture
def teacher(db):
    return make_user("enseignant@example.ga", User.AccountType.TEACHER_AUTHOR)


@pytest.fixture
def moderator(db):
    return make_user("mod@bibliogabon.ga", User.AccountType.CONTENT_ADMIN)


@pytest.fixture
def document(db, teacher):
    domain = AcademicDomain.objects.create(name="Droit", slug="droit")
    doc_type = DocumentType.objects.create(name="Cours", slug="cours")
    document = Document.objects.create(
        title="Un cours",
        slug="un-cours",
        academic_domain=domain,
        document_type=doc_type,
        category=Document.Category.VOLUNTARY_TEACHER_DEPOSIT,
        access_model=Document.AccessModel.FREE,
    )
    author = Author.objects.create(
        display_name=teacher.email, normalized_name=teacher.email, linked_user=teacher
    )
    DocumentAuthor.objects.create(
        document=document, author=author, role=DocumentAuthor.Role.AUTHOR
    )
    return document


@pytest.fixture
def api():
    return APIClient()


def declaration(document, **overrides):
    payload = {
        "agreement_type": RightsAgreement.AgreementType.TEACHER_VOLUNTARY,
        "rights_holder_name": "Prof X",
        "access_model": document.access_model,
        "withdrawal_rule": RightsAgreement.WithdrawalRule.AUTHOR_REQUEST,
    }
    payload.update(overrides)
    return payload


# --- Auteurs -----------------------------------------------------------------


def test_attaching_an_author_assigns_the_next_position(api, teacher, document):
    other = Author.objects.create(display_name="Co", normalized_name="co")
    api.force_authenticate(teacher)

    response = api.post(
        reverse(AUTHORS, args=[document.pk]),
        {"author": other.pk, "role": DocumentAuthor.Role.COAUTHOR},
        format="json",
    )

    assert response.status_code == 201, response.json()
    entry = DocumentAuthor.objects.get(document=document, author=other)
    assert entry.position == 2
    assert entry.role == DocumentAuthor.Role.COAUTHOR


def test_attaching_the_same_author_twice_is_refused(api, teacher, document):
    existing = DocumentAuthor.objects.get(document=document).author
    api.force_authenticate(teacher)

    response = api.post(
        reverse(AUTHORS, args=[document.pk]), {"author": existing.pk}, format="json"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "author_already_attached"


def test_detaching_leaves_the_ordering_contiguous(api, teacher, document):
    api.force_authenticate(teacher)
    for name in ("b", "c"):
        author = Author.objects.create(display_name=name, normalized_name=name)
        api.post(reverse(AUTHORS, args=[document.pk]), {"author": author.pk}, format="json")
    first = DocumentAuthor.objects.get(document=document, position=1)

    response = api.delete(reverse(AUTHOR_DETAIL, args=[document.pk, first.author_id]))

    assert response.status_code == 204
    positions = list(
        DocumentAuthor.objects.filter(document=document)
        .order_by("position")
        .values_list("position", flat=True)
    )
    assert positions == [1, 2], positions


def test_a_teacher_cannot_touch_the_authors_of_someone_elses_document(api, document):
    intruder = make_user("intrus@example.ga", User.AccountType.TEACHER_AUTHOR)
    api.force_authenticate(intruder)

    response = api.post(reverse(AUTHORS, args=[document.pk]), {"author": 1}, format="json")

    assert response.status_code == 404


# --- Déclaration de droits ---------------------------------------------------


def test_a_teacher_declares_the_rights(api, teacher, document):
    api.force_authenticate(teacher)

    response = api.put(
        reverse(RIGHTS, args=[document.pk]), declaration(document), format="json"
    )

    assert response.status_code == 200, response.json()
    agreement = RightsAgreement.objects.get(document=document)
    assert agreement.rights_holder_name == "Prof X"
    assert agreement.authorization_status == RightsAgreement.AuthorizationStatus.PENDING_REVIEW


def test_a_depositor_cannot_approve_their_own_declaration(api, teacher, document):
    """Le point le plus sensible : s'auto-certifier ferait s'effondrer toute
    la gouvernance des droits."""
    api.force_authenticate(teacher)

    api.put(
        reverse(RIGHTS, args=[document.pk]),
        declaration(
            document,
            authorization_status=RightsAgreement.AuthorizationStatus.APPROVED,
            reviewer_decision="Je m'auto-approuve",
            audit_reference="FAUX-001",
        ),
        format="json",
    )

    agreement = RightsAgreement.objects.get(document=document)
    assert agreement.authorization_status == RightsAgreement.AuthorizationStatus.PENDING_REVIEW
    assert agreement.reviewer_decision == ""
    assert agreement.audit_reference == ""


def test_a_teacher_cannot_reach_the_decision_endpoint(api, teacher, document):
    api.put(reverse(RIGHTS, args=[document.pk]), declaration(document), format="json")
    api.force_authenticate(teacher)

    response = api.post(
        reverse(DECISION, args=[document.pk]),
        {"decision": "approved", "reviewer_decision": "ok", "audit_reference": "X"},
        format="json",
    )

    assert response.status_code == 403


def test_a_declaration_can_be_replaced_before_review(api, teacher, document):
    api.force_authenticate(teacher)
    api.put(reverse(RIGHTS, args=[document.pk]), declaration(document), format="json")

    api.put(
        reverse(RIGHTS, args=[document.pk]),
        declaration(document, rights_holder_name="Université Omar Bongo"),
        format="json",
    )

    assert RightsAgreement.objects.filter(document=document).count() == 1
    assert RightsAgreement.objects.get(document=document).rights_holder_name == (
        "Université Omar Bongo"
    )


# --- Décision du relecteur ---------------------------------------------------


def declare_as_teacher(api, teacher, document, **overrides):
    api.force_authenticate(teacher)
    api.put(
        reverse(RIGHTS, args=[document.pk]), declaration(document, **overrides), format="json"
    )
    api.force_authenticate(None)


def test_a_moderator_approves_and_the_system_stamps_the_date(api, teacher, moderator, document):
    declare_as_teacher(api, teacher, document)
    api.force_authenticate(moderator)

    response = api.post(
        reverse(DECISION, args=[document.pk]),
        {
            "decision": "approved",
            "reviewer_decision": "Contrat de dépôt volontaire vérifié.",
            "audit_reference": "BG-CONTRAT-2026-014",
        },
        format="json",
    )

    assert response.status_code == 200, response.json()
    agreement = RightsAgreement.objects.get(document=document)
    assert agreement.authorization_status == RightsAgreement.AuthorizationStatus.APPROVED
    assert agreement.authorization_date is not None, "la date est horodatée par le système"
    assert agreement.audit_reference == "BG-CONTRAT-2026-014"
    event = AuditLog.objects.order_by("-id").first()
    assert event.event_type == "rights_agreement_approved"
    assert event.actor_id == moderator.pk


def test_an_approval_without_an_audit_reference_is_refused(api, teacher, moderator, document):
    """La référence d'audit est le lien vers le contrat signé : sans elle,
    l'approbation n'est pas traçable."""
    declare_as_teacher(api, teacher, document)
    api.force_authenticate(moderator)

    response = api.post(
        reverse(DECISION, args=[document.pk]),
        {"decision": "approved", "reviewer_decision": "ok"},
        format="json",
    )

    assert response.status_code == 400
    assert "audit_reference" in response.json()["error"]["field_errors"]


def test_a_rejection_requires_a_reason(api, teacher, moderator, document):
    """« Les documents rejetés doivent conserver un motif pour l'audit. »"""
    declare_as_teacher(api, teacher, document)
    api.force_authenticate(moderator)

    response = api.post(
        reverse(DECISION, args=[document.pk]),
        {"decision": "rejected", "reviewer_decision": "Non conforme"},
        format="json",
    )

    assert response.status_code == 400
    assert "rejection_reason" in response.json()["error"]["field_errors"]


def test_a_rejection_is_recorded_with_its_reason(api, teacher, moderator, document):
    declare_as_teacher(api, teacher, document)
    api.force_authenticate(moderator)

    response = api.post(
        reverse(DECISION, args=[document.pk]),
        {
            "decision": "rejected",
            "reviewer_decision": "Ayant droit non établi.",
            "rejection_reason": "Aucun contrat fourni.",
        },
        format="json",
    )

    assert response.status_code == 200
    agreement = RightsAgreement.objects.get(document=document)
    assert agreement.authorization_status == RightsAgreement.AuthorizationStatus.REJECTED
    assert agreement.rejection_reason == "Aucun contrat fourni."
    assert AuditLog.objects.order_by("-id").first().event_type == "rights_agreement_rejected"


def test_approval_makes_the_document_publishable(api, teacher, moderator, document):
    declare_as_teacher(api, teacher, document)
    api.force_authenticate(moderator)

    api.post(
        reverse(DECISION, args=[document.pk]),
        {
            "decision": "approved",
            "reviewer_decision": "Vérifié.",
            "audit_reference": "BG-CONTRAT-2026-015",
        },
        format="json",
    )

    from catalog.services import document_is_publishable

    document.refresh_from_db()
    assert document_is_publishable(document) is True
