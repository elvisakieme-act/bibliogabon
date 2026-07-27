from __future__ import annotations

from catalog.models import Document, RightsAgreement


def document_is_publishable(document: Document) -> bool:
    if not document.title or not document.academic_domain_id:
        return False
    if not document.document_authors.exists():
        return False
    try:
        rights_agreement = document.rights_agreement
    except RightsAgreement.DoesNotExist:
        return False
    return rights_agreement.is_valid_for_publication()
