from __future__ import annotations

import pytest

from document_processing.text import normalize_extracted_text


def test_repairs_the_quote_artefacts_seen_in_real_extraction():
    # Artefacts relevés sur la page 1 d'un vrai PDF ingéré :
    # « Mooc \x13 Comprendre la 4G \x14 »
    raw = "Mooc \x13 Comprendre la 4G \x14"

    assert normalize_extracted_text(raw) == "Mooc « Comprendre la 4G »"


def test_strips_other_control_characters():
    raw = "Institut\x00 Mines\x07-Telecom\x1f"

    assert normalize_extracted_text(raw) == "Institut Mines-Telecom"


def test_keeps_newlines_and_tabs_as_layout():
    raw = "Titre\nSous-titre\n\tIndente"

    assert normalize_extracted_text(raw) == "Titre\nSous-titre\n\tIndente"


def test_collapses_runs_of_spaces_without_losing_paragraphs():
    raw = "Semaine 1  :   Architecture\n\n\n\nSemaine 2 : Securite"

    assert normalize_extracted_text(raw) == "Semaine 1 : Architecture\n\nSemaine 2 : Securite"


def test_trims_leading_and_trailing_whitespace():
    assert normalize_extracted_text("  \n texte \n  ") == "texte"


def test_leaves_clean_text_untouched():
    clean = "Architecture et principes generaux,\nSemaine 1"

    assert normalize_extracted_text(clean) == clean


@pytest.mark.parametrize("value", ["", "   ", "\n\n"])
def test_blank_input_normalises_to_empty(value):
    assert normalize_extracted_text(value) == ""
