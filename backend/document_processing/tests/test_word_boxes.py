"""Position des mots sur la page.

Le lecteur superpose une couche texte transparente à l'image de la page. Cette
couche ne vaut que si elle est *alignée* : un décalage ne produit aucune erreur,
aucune exception, aucun test rouge — seulement une sélection qui attrape le
mauvais mot, et un lecteur d'écran qui lit à côté. C'est un défaut silencieux,
donc il lui faut des tests explicites.

Deux invariants :

- **Les positions sont des fractions, pas des pixels.** La largeur de rendu est
  un réglage. Des pixels se décaleraient le jour où il change, sans rien
  signaler.
- **Les positions décrivent le texte stocké.** Texte et positions viennent de
  la même passe d'extraction : un mot sélectionnable absent du texte indexé
  serait une seconde vérité sur la même page.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.core.exceptions import ValidationError

from catalog.models import AcademicDomain, Document, DocumentType
from document_ingestion.pipeline import ingest_document_file
from document_processing.models import DocumentPage, ExtractedText

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "document_ingestion"
    / "tests"
    / "fixtures"
    / "sample-3-pages.pdf"
)


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def ingested(db, local_storage):
    domain = AcademicDomain.objects.create(name="Positions", slug="positions")
    document_type = DocumentType.objects.create(name="Cours", slug="cours-positions")
    document = Document.objects.create(
        title="Document positionné",
        slug="document-positionne",
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
    )
    with FIXTURE.open("rb") as handle:
        return ingest_document_file(
            document=document, fileobj=handle, original_filename="s.pdf"
        )


def first_page_text(version) -> ExtractedText:
    page = DocumentPage.objects.get(version=version, page_number=1)
    return ExtractedText.objects.get(page=page)


@pytest.mark.django_db
def test_ingestion_records_a_position_for_every_word(ingested):
    extracted = first_page_text(ingested)

    assert extracted.word_boxes, "l'ingestion devrait produire des positions"
    assert all(len(box) == 5 for box in extracted.word_boxes)


@pytest.mark.django_db
def test_positions_are_fractions_of_the_page_not_pixels(ingested):
    """Une seule coordonnée au-delà de 1 trahirait un stockage en pixels."""
    extracted = first_page_text(ingested)

    for x0, y0, x1, y1, word in extracted.word_boxes:
        assert 0 <= x0 <= 1 and 0 <= x1 <= 1, f"{word} : abscisses hors page"
        assert 0 <= y0 <= 1 and 0 <= y1 <= 1, f"{word} : ordonnées hors page"


@pytest.mark.django_db
def test_boxes_are_not_degenerate(ingested):
    """Une boîte de largeur nulle ne peut pas être sélectionnée à l'écran."""
    extracted = first_page_text(ingested)

    for x0, y0, x1, y1, word in extracted.word_boxes:
        assert x1 > x0, f"{word} : largeur nulle ou négative"
        assert y1 > y0, f"{word} : hauteur nulle ou négative"


@pytest.mark.django_db
def test_every_positioned_word_appears_in_the_stored_text(ingested):
    """Texte et positions décrivent la même page.

    C'est la raison pour laquelle l'extraction est passée à une seule
    bibliothèque. Avec deux extracteurs, un mot pouvait être sélectionnable
    sans figurer dans le texte indexé — et la recherche interne aurait alors
    contredit ce que le lecteur affiche.
    """
    extracted = first_page_text(ingested)
    stored = " ".join(extracted.text.split())

    for box in extracted.word_boxes:
        assert box[4] in stored, f"{box[4]!r} est positionné mais absent du texte"


@pytest.mark.django_db
def test_the_layer_reads_in_the_same_order_as_the_stored_text(ingested):
    """L'ordre de la couche est l'ordre du texte.

    Une première version de ce test vérifiait que les ordonnées croissaient.
    Elle passait — sur une page à une colonne. Elle aurait échoué sur la
    première thèse en deux colonnes, où l'ordre de lecture descend une colonne
    puis remonte : ce test-là décrivait la fixture, pas le système.

    L'invariant réel est que la couche transparente et le texte stocké
    racontent la page dans le même ordre. C'est ce qu'un lecteur d'écran
    parcourt, et c'est ce que la recherche interne indexe.
    """
    extracted = first_page_text(ingested)
    positioned = [box[4] for box in extracted.word_boxes]
    stored = extracted.text.split()

    assert positioned == stored, (
        "la couche texte et le texte stocké ne racontent pas la page dans le même ordre"
    )


@pytest.mark.django_db
def test_a_reextraction_without_positions_clears_the_previous_ones(ingested):
    """Des positions orphelines décriraient un texte qui n'est plus là."""
    from document_processing.services import attach_extracted_text

    page = DocumentPage.objects.get(version=ingested, page_number=1)
    assert ExtractedText.objects.get(page=page).word_boxes

    attach_extracted_text(page=page, text="Texte corrigé à la main.")

    assert ExtractedText.objects.get(page=page).word_boxes == []


@pytest.mark.django_db
def test_a_malformed_box_is_refused_at_write_time(ingested):
    """Le défaut doit échouer à l'écriture, pas au rendu dans le navigateur."""
    extracted = first_page_text(ingested)

    for invalid, why in (
        ([[0.1, 0.1, 0.2]], "quatre éléments au lieu de cinq"),
        ([[0.1, 0.1, 0.2, 0.2, ""]], "mot vide"),
        ([[0.1, 0.1, 1.4, 0.2, "hors"]], "coordonnée au-delà de 1"),
        ([[-0.1, 0.1, 0.2, 0.2, "avant"]], "coordonnée négative"),
        ([[0.1, 0.1, 0.2, 0.2, 42]], "mot qui n'est pas une chaîne"),
        ("pas une liste", "valeur qui n'est pas une liste"),
    ):
        extracted.word_boxes = invalid
        try:
            extracted.save()
        except ValidationError:
            continue
        pytest.fail(f"accepté à tort : {why}")
