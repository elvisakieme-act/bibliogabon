"""Les listes de choix de l'écran doivent couvrir les énumérations du serveur.

Sept listes TypeScript reproduisent des `TextChoices` Python. Une valeur
ajoutée côté serveur et absente de l'écran devient **non sélectionnable**, en
silence : le déposant ne peut simplement pas choisir la nouvelle catégorie, et
rien n'échoue.

Les états de publication et les codes de complétude dégradent proprement — ils
s'affichent tels quels quand l'écran ne les connaît pas — mais une liste de
choix, non. Ce test lit les fichiers du dépôt : il n'exécute pas TypeScript, il
vérifie seulement que chaque valeur y figure. C'est grossier, et c'est
suffisant pour que la dérive échoue en CI plutôt que d'attendre un utilisateur.

Un chemin introuvable **échoue** au lieu de sauter. Un saut silencieux ferait
disparaître le garde-fou à la première réorganisation, ce qui est précisément
le défaut qu'on vient de corriger sur les tests d'OCR : huit d'entre eux se
sautaient sans bruit et un neuvième est resté rouge vingt-huit exécutions
durant.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from accounts.models import OrganizationMembership
from catalog.models import Document, DocumentAuthor, RightsAgreement
from catalog.services import (
    INVALID_ACCESS_MODEL,
    INVALID_CATEGORY,
    MISSING_ACADEMIC_DOMAIN,
    MISSING_AUTHOR,
    MISSING_DOCUMENT_TYPE,
    MISSING_RIGHTS_AGREEMENT,
    MISSING_RIGHTS_HOLDER,
    MISSING_STUDENT_CONSENT,
    MISSING_TITLE,
    MISSING_WITHDRAWAL_RULE,
    RIGHTS_ACCESS_MODEL_MISMATCH,
    RIGHTS_NOT_APPROVED,
)
from operations.models import PublicationReview, SupportTicket

FRONTEND = Path(__file__).resolve().parents[5] / "frontend" / "src" / "components" / "staff"

CASES = [
    ("options.ts", "CATEGORY_OPTIONS", Document.Category.values),
    (
        "../../routes/gestion/ReviewsPage.tsx",
        "REVIEW_STATUS_OPTIONS",
        PublicationReview.Status.values,
    ),
    ("ticketLabels.ts", "CATEGORY_LABELS", SupportTicket.Category.values),
    ("ticketLabels.ts", "STATUS_LABELS", SupportTicket.Status.values),
    ("ticketLabels.ts", "PRIORITY_LABELS", SupportTicket.Priority.values),
    (
        "membershipLabels.ts",
        "MEMBERSHIP_STATUS_LABELS",
        OrganizationMembership.Status.values,
    ),
    (
        "membershipLabels.ts",
        "VERIFICATION_STATUS_LABELS",
        __import__(
            "accounts.models", fromlist=["x"]
        ).OrganizationMembership.VerificationStatus.values,
    ),
    ("options.ts", "ACCESS_MODEL_OPTIONS", Document.AccessModel.values),
    ("publicationStatus.ts", "PUBLICATION_STATUS_LABELS", Document.PublicationStatus.values),
    ("rightsOptions.ts", "AGREEMENT_TYPE_OPTIONS", RightsAgreement.AgreementType.values),
    ("rightsOptions.ts", "WITHDRAWAL_RULE_OPTIONS", RightsAgreement.WithdrawalRule.values),
    (
        "rightsOptions.ts",
        "AUTHORIZATION_STATUS_LABELS",
        RightsAgreement.AuthorizationStatus.values,
    ),
    ("rightsOptions.ts", "AUTHOR_ROLE_OPTIONS", DocumentAuthor.Role.values),
    (
        "completeness.ts",
        "LABELS",
        [
            MISSING_TITLE,
            MISSING_ACADEMIC_DOMAIN,
            MISSING_DOCUMENT_TYPE,
            INVALID_CATEGORY,
            INVALID_ACCESS_MODEL,
            MISSING_AUTHOR,
            MISSING_RIGHTS_AGREEMENT,
            MISSING_RIGHTS_HOLDER,
            MISSING_WITHDRAWAL_RULE,
            RIGHTS_ACCESS_MODEL_MISMATCH,
            MISSING_STUDENT_CONSENT,
            RIGHTS_NOT_APPROVED,
        ],
    ),
]


def read_declaration(filename: str, name: str) -> str:
    """Isole le texte d'une déclaration, pour qu'une valeur présente dans une
    autre liste du même fichier ne fasse pas passer le test à tort."""
    source = (FRONTEND / filename).read_text(encoding="utf-8")
    start = source.index(name)
    remainder = source[start:]
    end = remainder.index("\n};") if "\n};" in remainder else len(remainder)
    closing = remainder.index("\n];") if "\n];" in remainder else len(remainder)
    return remainder[: min(end, closing)]


def declares(declaration: str, value: str) -> bool:
    """Deux ecritures coexistent : `{ value: "..." }` pour une table de
    libelles, `{ value: "..." }` quote pour une liste d'options. On accepte
    les deux plutot que d'imposer un style au frontend."""
    if f'"{value}"' in declaration:
        return True
    return bool(re.search(rf"(?m)^\s*{re.escape(value)}\s*:", declaration))


@pytest.mark.parametrize(("filename", "name", "values"), CASES, ids=[c[1] for c in CASES])
def test_the_screen_covers_every_server_value(filename, name, values):
    assert FRONTEND.is_dir(), (
        f"{FRONTEND} est introuvable. Si le frontend a bouge, corrigez ce "
        f"chemin : sauter le test ferait disparaitre le garde-fou en silence."
    )
    declaration = read_declaration(filename, name)
    missing = [value for value in values if not declares(declaration, value)]

    assert not missing, (
        f"{name} dans frontend/src/components/staff/{filename} ne couvre pas "
        f"{missing}. Une valeur absente est non selectionnable a l'ecran, sans "
        f"qu'aucune erreur ne le signale."
    )
