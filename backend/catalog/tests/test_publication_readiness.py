import pytest
from django.utils import timezone

from catalog.models import AcademicDomain, Author, Document, DocumentAuthor, RightsAgreement
from catalog.services import document_is_publishable


@pytest.mark.django_db
def test_document_without_rights_agreement_is_not_publishable():
    domain = AcademicDomain.objects.create(name="Droit", slug="droit")
    document = Document.objects.create(
        title="Droit public gabonais",
        slug="droit-public-gabonais",
        academic_domain=domain,
        category=Document.Category.STUDENT_WORK,
        access_model=Document.AccessModel.RESTRICTED,
    )
    author = Author.objects.create(display_name="Aline NZE", normalized_name="nze aline")
    DocumentAuthor.objects.create(document=document, author=author)

    assert document_is_publishable(document) is False


@pytest.mark.django_db
def test_document_with_complete_approved_rights_is_publishable():
    domain = AcademicDomain.objects.create(name="Medecine", slug="medecine")
    document = Document.objects.create(
        title="Sante publique au Gabon",
        slug="sante-publique-gabon",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )
    author = Author.objects.create(display_name="Brice ONDO", normalized_name="ondo brice")
    DocumentAuthor.objects.create(document=document, author=author)
    RightsAgreement.objects.create(
        document=document,
        rights_holder_name="Brice ONDO",
        agreement_type=RightsAgreement.AgreementType.OPEN_LICENSE,
        authorization_status=RightsAgreement.AuthorizationStatus.APPROVED,
        authorization_date=timezone.now().date(),
        access_model=Document.AccessModel.FREE,
        withdrawal_rule=RightsAgreement.WithdrawalRule.LICENSE_INVALID,
        reviewer_decision="Open license verified for publication.",
        audit_reference="BG-AUDIT-2026-0001",
    )

    assert document_is_publishable(document) is True


@pytest.mark.django_db
def test_rights_access_model_must_match_document_access_model_to_publish():
    domain = AcademicDomain.objects.create(name="Economie", slug="economie")
    document = Document.objects.create(
        title="Economie gabonaise",
        slug="economie-gabonaise",
        academic_domain=domain,
        category=Document.Category.COMMERCIAL_PARTNER_CONTENT,
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    author = Author.objects.create(display_name="Carine MBA", normalized_name="mba carine")
    DocumentAuthor.objects.create(document=document, author=author)
    RightsAgreement.objects.create(
        document=document,
        rights_holder_name="Carine MBA",
        agreement_type=RightsAgreement.AgreementType.COMMERCIAL_DISTRIBUTION,
        authorization_status=RightsAgreement.AuthorizationStatus.APPROVED,
        authorization_date=timezone.now().date(),
        access_model=Document.AccessModel.FREE,
        withdrawal_rule=RightsAgreement.WithdrawalRule.COMMERCIAL_TERMS,
        reviewer_decision="Commercial terms reviewed.",
        audit_reference="BG-AUDIT-2026-0002",
    )

    assert document_is_publishable(document) is False
