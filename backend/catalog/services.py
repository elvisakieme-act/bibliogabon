from __future__ import annotations

from catalog.models import Document, DocumentAuthor, RightsAgreement


def document_is_publishable(document: Document) -> bool:
    if not document.title or not document.academic_domain_id:
        return False
    if document.category not in Document.Category.values:
        return False
    if document.access_model not in Document.AccessModel.values:
        return False
    if not document.document_authors.filter(
        role__in=[DocumentAuthor.Role.AUTHOR, DocumentAuthor.Role.COAUTHOR],
    ).exists():
        return False
    try:
        rights_agreement = document.rights_agreement
    except RightsAgreement.DoesNotExist:
        return False
    return rights_agreement.is_valid_for_publication()
