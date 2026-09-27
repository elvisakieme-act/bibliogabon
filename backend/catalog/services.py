"""Règles de complétude d'un document.

Deux portes, délibérément distinctes, conformes au workflow de gouvernance
`draft → submitted → rights_review → … → published` :

- **déposer** exige une *déclaration* complète ;
- **publier** exige que cette déclaration ait été *approuvée* par un
  relecteur.

Les confondre rendrait tout dépôt impossible, puisque l'approbation est
l'acte du relecteur et survient après la soumission.
"""

from __future__ import annotations

from catalog.models import Document, DocumentAuthor, RightsAgreement

# Codes stables : ils voyagent jusqu'à l'API et jusqu'à l'écran de dépôt,
# qui doit dire à un déposant ce qu'il lui reste à fournir.
MISSING_TITLE = "title"
MISSING_ACADEMIC_DOMAIN = "academic_domain"
MISSING_DOCUMENT_TYPE = "document_type"
INVALID_CATEGORY = "category"
INVALID_ACCESS_MODEL = "access_model"
MISSING_AUTHOR = "author"
MISSING_RIGHTS_AGREEMENT = "rights_agreement"
MISSING_RIGHTS_HOLDER = "rights_holder"
MISSING_WITHDRAWAL_RULE = "withdrawal_rule"
RIGHTS_ACCESS_MODEL_MISMATCH = "rights_access_model_mismatch"
MISSING_STUDENT_CONSENT = "student_consent_reference"
RIGHTS_NOT_APPROVED = "rights_agreement_not_approved"


def _missing_metadata(document: Document) -> list[str]:
    missing: list[str] = []
    if not document.title:
        missing.append(MISSING_TITLE)
    if not document.academic_domain_id:
        missing.append(MISSING_ACADEMIC_DOMAIN)
    if not document.document_type_id:
        missing.append(MISSING_DOCUMENT_TYPE)
    if document.category not in Document.Category.values:
        missing.append(INVALID_CATEGORY)
    if document.access_model not in Document.AccessModel.values:
        missing.append(INVALID_ACCESS_MODEL)
    if not document.document_authors.filter(
        role__in=[DocumentAuthor.Role.AUTHOR, DocumentAuthor.Role.COAUTHOR],
    ).exists():
        missing.append(MISSING_AUTHOR)
    return missing


def _missing_rights_declaration(document: Document, agreement: RightsAgreement) -> list[str]:
    """Ce que le déposant doit déclarer, avant toute vérification."""
    missing: list[str] = []
    if not agreement.rights_holder_name:
        missing.append(MISSING_RIGHTS_HOLDER)
    if not agreement.withdrawal_rule:
        missing.append(MISSING_WITHDRAWAL_RULE)
    if agreement.access_model != document.access_model:
        # Autoriser une diffusion libre puis vendre le document par
        # abonnement est précisément la faute que cette règle empêche.
        missing.append(RIGHTS_ACCESS_MODEL_MISMATCH)
    if document.category == Document.Category.STUDENT_WORK and not agreement.consent_reference:
        # « Les travaux d'étudiants exigent un consentement explicite. »
        missing.append(MISSING_STUDENT_CONSENT)
    return missing


def missing_deposit_requirements(document: Document) -> list[str]:
    """Ce qu'il manque pour soumettre le document à la revue."""
    missing = _missing_metadata(document)
    try:
        agreement = document.rights_agreement
    except RightsAgreement.DoesNotExist:
        missing.append(MISSING_RIGHTS_AGREEMENT)
    else:
        missing.extend(_missing_rights_declaration(document, agreement))
    return missing


def missing_publication_requirements(document: Document) -> list[str]:
    """Ce qu'il manque pour publier : la déclaration, puis son approbation."""
    missing = missing_deposit_requirements(document)
    try:
        agreement = document.rights_agreement
    except RightsAgreement.DoesNotExist:
        return missing
    if not agreement.is_valid_for_publication():
        missing.append(RIGHTS_NOT_APPROVED)
    return missing


def document_is_publishable(document: Document) -> bool:
    return not missing_publication_requirements(document)
