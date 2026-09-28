"""Ce qu'un lecteur peut faire du texte d'une page.

La couche texte rend la page sélectionnable, cherchable et lisible par un
lecteur d'écran — et copiable. Une plateforme où l'on copie un mémoire entier
ne tient pas ce qu'elle promet à ses déposants.

La règle suit l'accord de droits signé plutôt qu'un réglage global, parce
qu'un réglage uniforme trahirait soit les auteurs, soit l'accès ouvert.

Ce que ces tests ne prouvent pas, et qu'il faut dire : `selectable` et
`protected` envoient le même texte. Empêcher la sélection **dissuade**, ne
protège pas. Seul `withheld` protège, en n'envoyant rien — et c'est pourquoi
il coûte le lecteur d'écran.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from catalog.models import AcademicDomain, Document, DocumentType, RightsAgreement
from document_reader.services import TextLayerPolicy, text_layer_policy


def make_document(
    *,
    slug: str,
    category: str = Document.Category.STUDENT_WORK,
    access_model: str = Document.AccessModel.SUBSCRIPTION,
) -> Document:
    domain = AcademicDomain.objects.create(name=f"D {slug}", slug=f"d-{slug}")
    document_type = DocumentType.objects.create(name=f"T {slug}", slug=f"t-{slug}")
    return Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        document_type=document_type,
        category=category,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
        published_at=timezone.now(),
    )


def attach_rights(document: Document, **fields) -> RightsAgreement:
    defaults = {
        "rights_holder_name": "Titulaire",
        "agreement_type": RightsAgreement.AgreementType.STUDENT_CONSENT,
        "authorization_status": RightsAgreement.AuthorizationStatus.APPROVED,
        "access_model": document.access_model,
        "withdrawal_rule": RightsAgreement.WithdrawalRule.AUTHOR_REQUEST,
    }
    return RightsAgreement.objects.create(document=document, **{**defaults, **fields})


@pytest.mark.django_db
def test_an_open_resource_is_freely_selectable():
    """Rendre une ressource ouverte moins utilisable ici qu'ailleurs irait
    contre la raison d'être d'un dépôt ouvert."""
    document = make_document(
        slug="ouverte",
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )

    assert text_layer_policy(document) == TextLayerPolicy.SELECTABLE


@pytest.mark.django_db
def test_an_open_licence_agreement_is_freely_selectable():
    """La licence prime sur la catégorie : un fonds institutionnel déposé sous
    licence ouverte reste ouvert."""
    document = make_document(
        slug="licence-ouverte", category=Document.Category.INSTITUTIONAL_FUND
    )
    attach_rights(document, agreement_type=RightsAgreement.AgreementType.OPEN_LICENSE)

    assert text_layer_policy(document) == TextLayerPolicy.SELECTABLE


@pytest.mark.django_db
@pytest.mark.parametrize(
    "agreement_type",
    [
        RightsAgreement.AgreementType.STUDENT_CONSENT,
        RightsAgreement.AgreementType.TEACHER_VOLUNTARY,
        RightsAgreement.AgreementType.INSTITUTIONAL_ARCHIVE,
        RightsAgreement.AgreementType.COMMERCIAL_DISTRIBUTION,
    ],
)
def test_every_other_agreement_blocks_copying(agreement_type):
    document = make_document(slug=f"protege-{agreement_type}")
    attach_rights(document, agreement_type=agreement_type)

    assert text_layer_policy(document) == TextLayerPolicy.PROTECTED


@pytest.mark.django_db
def test_a_document_without_a_rights_agreement_is_not_the_most_permissive():
    """Un document dont les droits ne sont pas déclarés ne doit pas être le
    plus permissif du catalogue. C'est la direction du défaut qui compte : se
    tromper vers `protected` gêne un lecteur, se tromper vers `selectable`
    trahit un déposant."""
    document = make_document(slug="sans-accord")

    assert text_layer_policy(document) == TextLayerPolicy.PROTECTED


@pytest.mark.django_db
def test_a_confidentiality_clause_withholds_the_text_entirely():
    document = make_document(slug="confidentiel")
    attach_rights(document, confidentiality_terms="Diffusion interne uniquement.")

    assert text_layer_policy(document) == TextLayerPolicy.WITHHELD


@pytest.mark.django_db
def test_a_confidentiality_clause_beats_an_open_licence():
    """Les deux peuvent coexister dans la base. En cas de conflit, c'est la
    clause la plus restrictive qui s'applique — l'inverse publierait un
    document qu'un contrat interdit de diffuser."""
    document = make_document(slug="conflit", category=Document.Category.OPEN_RESOURCE)
    attach_rights(
        document,
        agreement_type=RightsAgreement.AgreementType.OPEN_LICENSE,
        confidentiality_terms="Clause de confidentialité.",
    )

    assert text_layer_policy(document) == TextLayerPolicy.WITHHELD


@pytest.mark.django_db
def test_a_blank_confidentiality_field_is_not_a_clause():
    """Le champ est vide par défaut sur tout le catalogue : le confondre avec
    une clause mettrait chaque document en image seule."""
    document = make_document(slug="blanc")
    attach_rights(document, confidentiality_terms="   ")

    assert text_layer_policy(document) != TextLayerPolicy.WITHHELD


@pytest.mark.django_db
def test_a_withheld_document_ships_no_word_positions(tmp_path, settings):
    """La politique doit *agir*, pas seulement se déclarer.

    Un `text_policy: "withheld"` accompagné des positions serait le pire des
    deux mondes : la promesse de protection et le texte quand même.
    """
    from pathlib import Path as _Path

    from document_ingestion.pipeline import ingest_document_file
    from document_reader.models import ReaderSession
    from document_reader.services import get_reader_page

    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)

    fixture = (
        _Path(__file__).resolve().parents[2]
        / "document_ingestion"
        / "tests"
        / "fixtures"
        / "sample-3-pages.pdf"
    )
    # En accès libre : une session anonyme suffit, et le test porte sur la
    # politique de copie, pas sur le droit de lecture.
    document = make_document(
        slug="retenu",
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )
    with fixture.open("rb") as handle:
        version = ingest_document_file(
            document=document, fileobj=handle, original_filename="s.pdf"
        )
    session = ReaderSession.objects.create(
        document=document,
        version=version,
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )

    ouvert = get_reader_page(session=session, page_number=1)
    assert ouvert["text_policy"] == TextLayerPolicy.SELECTABLE
    assert ouvert["words"], "une ressource ouverte doit porter ses positions"

    attach_rights(document, confidentiality_terms="Diffusion interne uniquement.")

    retenu = get_reader_page(session=session, page_number=1)
    assert retenu["text_policy"] == TextLayerPolicy.WITHHELD
    assert retenu["words"] == []
