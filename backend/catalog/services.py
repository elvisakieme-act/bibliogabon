from __future__ import annotations

from catalog.models import Document, DocumentAuthor, RightsAgreement


# Codes stables : ils voyagent jusqu'à l'API et jusqu'à l'écran de dépôt,
# qui doit dire à un enseignant ce qu'il lui reste à fournir.
MISSING_TITLE = "title"
MISSING_ACADEMIC_DOMAIN = "academic_domain"
MISSING_DOCUMENT_TYPE = "document_type"
INVALID_CATEGORY = "category"
INVALID_ACCESS_MODEL = "access_model"
MISSING_AUTHOR = "author"
MISSING_RIGHTS_AGREEMENT = "rights_agreement"
INVALID_RIGHTS_AGREEMENT = "rights_agreement_invalid"


def missing_publication_requirements(document: Document) -> list[str]:
    """Ce qu'il manque à un document pour être publiable.

    Source unique de la règle : `document_is_publishable` en dérive. Un
    booléen seul ne permettait pas de dire à un déposant ce qui bloque,
    et dupliquer la liste ailleurs aurait garanti la divergence.
    """
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

    try:
        rights_agreement = document.rights_agreement
    except RightsAgreement.DoesNotExist:
        missing.append(MISSING_RIGHTS_AGREEMENT)
    else:
        if not rights_agreement.is_valid_for_publication():
            missing.append(INVALID_RIGHTS_AGREEMENT)

    return missing


def document_is_publishable(document: Document) -> bool:
    return not missing_publication_requirements(document)
