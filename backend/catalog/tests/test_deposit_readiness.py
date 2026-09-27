from __future__ import annotations

import pytest
from django.utils import timezone

from catalog.models import (
    AcademicDomain, Author, Document, DocumentAuthor, DocumentType, RightsAgreement,
)
from catalog.services import (
    document_is_publishable,
    missing_deposit_requirements,
    missing_publication_requirements,
)


@pytest.fixture
def document(db):
    domain = AcademicDomain.objects.create(name="Droit", slug="droit")
    doc_type = DocumentType.objects.create(name="Cours", slug="cours")
    document = Document.objects.create(
        title="Un cours", slug="un-cours", academic_domain=domain, document_type=doc_type,
        category=Document.Category.VOLUNTARY_TEACHER_DEPOSIT,
        access_model=Document.AccessModel.FREE,
    )
    author = Author.objects.create(display_name="Prof X", normalized_name="prof x")
    DocumentAuthor.objects.create(
        document=document, author=author, role=DocumentAuthor.Role.AUTHOR
    )
    return document


def declare(document, **overrides):
    fields = {
        "agreement_type": RightsAgreement.AgreementType.TEACHER_VOLUNTARY,
        "rights_holder_name": "Prof X",
        "authorization_status": RightsAgreement.AuthorizationStatus.PENDING_REVIEW,
        "access_model": document.access_model,
        "withdrawal_rule": RightsAgreement.WithdrawalRule.AUTHOR_REQUEST,
    }
    fields.update(overrides)
    return RightsAgreement.objects.create(document=document, **fields)


def approve(agreement):
    agreement.authorization_status = RightsAgreement.AuthorizationStatus.APPROVED
    agreement.authorization_date = timezone.now().date()
    agreement.reviewer_decision = "Contrat vérifié."
    agreement.audit_reference = "BG-CONTRAT-2026-014"
    agreement.save()
    return agreement


def test_a_complete_declaration_is_enough_to_submit(document):
    """Le relecteur approuve APRES la soumission : exiger l'approbation pour
    soumettre rendrait tout dépôt impossible."""
    declare(document)

    assert missing_deposit_requirements(document) == []


def test_a_complete_declaration_is_not_enough_to_publish(document):
    declare(document)

    assert missing_publication_requirements(document) != []
    assert document_is_publishable(document) is False


def test_an_approved_declaration_is_enough_to_publish(document):
    approve(declare(document))

    assert missing_publication_requirements(document) == []
    assert document_is_publishable(document) is True


def test_a_missing_declaration_blocks_submission(document):
    assert "rights_agreement" in missing_deposit_requirements(document)


def test_an_incomplete_declaration_names_each_gap(document):
    declare(document, rights_holder_name="", withdrawal_rule="")

    missing = missing_deposit_requirements(document)

    assert "rights_holder" in missing
    assert "withdrawal_rule" in missing


def test_an_access_model_mismatch_blocks_submission(document):
    """Autoriser une diffusion libre puis vendre le document par abonnement
    est exactement la faute que cette règle empêche."""
    declare(document, access_model=Document.AccessModel.SUBSCRIPTION)

    assert "rights_access_model_mismatch" in missing_deposit_requirements(document)


def test_a_student_work_requires_an_explicit_consent_reference(document):
    """« Les travaux d'étudiants exigent un consentement explicite. »"""
    document.category = Document.Category.STUDENT_WORK
    document.save(update_fields=["category"])
    declare(document, agreement_type=RightsAgreement.AgreementType.STUDENT_CONSENT)

    assert "student_consent_reference" in missing_deposit_requirements(document)


def test_a_student_work_with_a_consent_reference_may_be_submitted(document):
    document.category = Document.Category.STUDENT_WORK
    document.save(update_fields=["category"])
    declare(
        document,
        agreement_type=RightsAgreement.AgreementType.STUDENT_CONSENT,
        consent_reference="CONSENT-2026-031",
    )

    assert missing_deposit_requirements(document) == []


def test_other_categories_do_not_require_a_consent_reference(document):
    declare(document)

    assert "student_consent_reference" not in missing_deposit_requirements(document)
