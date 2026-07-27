from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion, ProcessingJob
from document_processing.models import DocumentPage, ExtractedText
from document_processing.services import attach_extracted_text, create_page_records


def create_version(version_label="v1"):
    domain = AcademicDomain.objects.create(name=f"Lettres {version_label}", slug=f"lettres-{version_label}")
    document = Document.objects.create(
        title=f"Corpus {version_label}",
        slug=f"corpus-{version_label}",
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.PRIVATE,
    )
    return DocumentVersion.objects.create(document=document, version_label=version_label)


def create_page():
    version = create_version()
    return create_page_records(version=version, page_count=1)[0]


@pytest.mark.django_db
def test_attach_extracted_text_stores_page_text_metadata():
    page = create_page()

    extracted = attach_extracted_text(
        page=page,
        text="Chapitre 1. Introduction aux archives numeriques.",
        language_code="fr",
        extraction_method=ExtractedText.ExtractionMethod.TEXT_LAYER,
        confidence=0.98,
    )

    assert extracted.page == page
    assert extracted.text == "Chapitre 1. Introduction aux archives numeriques."
    assert extracted.language_code == "fr"
    assert extracted.extraction_method == ExtractedText.ExtractionMethod.TEXT_LAYER
    assert extracted.confidence == Decimal("0.98")


@pytest.mark.django_db
def test_attach_extracted_text_updates_existing_page_text():
    page = create_page()
    first = attach_extracted_text(page=page, text="Ancien texte.")

    second = attach_extracted_text(page=page, text="Texte revise.", extraction_method=ExtractedText.ExtractionMethod.MANUAL)

    assert second.pk == first.pk
    assert ExtractedText.objects.count() == 1
    assert second.text == "Texte revise."
    assert second.extraction_method == ExtractedText.ExtractionMethod.MANUAL


@pytest.mark.django_db
def test_attach_extracted_text_rejects_blank_text():
    with pytest.raises(ValueError):
        attach_extracted_text(page=create_page(), text="   ")


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
@pytest.mark.django_db
def test_extracted_text_save_rejects_confidence_outside_zero_to_one(confidence):
    text = ExtractedText(page=create_page(), text="Contenu lisible.", confidence=confidence)

    with pytest.raises(ValidationError):
        text.save()


@pytest.mark.django_db
def test_extracted_text_save_rejects_processing_job_from_other_version():
    page = create_page()
    other_version = create_version(version_label="v2")
    other_job = ProcessingJob.objects.create(
        version=other_version,
        job_type=ProcessingJob.JobType.OCR,
        idempotency_key="other-version-text-job",
    )
    text = ExtractedText(page=page, text="Contenu lisible.", created_by_job=other_job)

    with pytest.raises(ValidationError):
        text.save()
