"""Normalisation du texte extrait, appliquée en un seul point.

Les extracteurs PDF rendent souvent les guillemets typographiques sous forme
de caractères de contrôle : sur un vrai document ingéré, « Mooc « Comprendre
la 4G » » ressortait en `Mooc \x13 Comprendre la 4G \x14`. Sans traitement,
ces octets atteignent `ExtractedText`, l'index de recherche, puis le lecteur.

La couche texte et l'OCR passent tous deux par cette fonction, de sorte
qu'aucun chemin d'extraction ne puisse réintroduire le problème.
"""

from __future__ import annotations

import re
import unicodedata

# Substitutions constatées sur des PDF réels : les extracteurs émettent ces
# codes de contrôle à la place des guillemets français.
CONTROL_SUBSTITUTIONS = {
    "\x13": "«",
    "\x14": "»",
}

# Contrôles C0/C1 à supprimer, en préservant tabulation et sauts de ligne qui
# portent la mise en page.
_LAYOUT_WHITESPACE = {"\t", "\n"}
# Les tabulations portent l'indentation : on les garde, on n'écrase que
# les suites d'espaces.
_HORIZONTAL_RUN = re.compile(r"[^\S\n\t]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_ON_LINE = re.compile(r"[^\S\n]+\n")


def normalize_extracted_text(text: str) -> str:
    if not text:
        return ""

    for source, replacement in CONTROL_SUBSTITUTIONS.items():
        text = text.replace(source, replacement)

    text = "".join(
        character
        for character in text
        if character in _LAYOUT_WHITESPACE or unicodedata.category(character) != "Cc"
    )

    text = _HORIZONTAL_RUN.sub(" ", text)
    text = _TRAILING_ON_LINE.sub("\n", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()
