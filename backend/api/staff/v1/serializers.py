"""Formes des réponses staff.

Règle unique et non négociable : rien de ce qui touche au stockage ne
sort d'ici. Ni clé, ni bucket, ni URL. Le back-office affiche des états,
pas des chemins de fichier.
"""

from __future__ import annotations

from rest_framework import serializers

from catalog.models import Document, DocumentAuthor
from catalog.services import (
    missing_deposit_requirements,
    missing_publication_requirements,
)


class StaffAuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="author_id", read_only=True)
    display_name = serializers.CharField(source="author.display_name", read_only=True)
    role = serializers.CharField(read_only=True)
    position = serializers.IntegerField(read_only=True)


class StaffRightsSerializer(serializers.Serializer):
    agreement_type = serializers.CharField(read_only=True)
    rights_holder_name = serializers.CharField(read_only=True)
    authorization_status = serializers.CharField(read_only=True)
    withdrawal_rule = serializers.CharField(read_only=True)
    valid_for_publication = serializers.BooleanField(read_only=True)


class StaffIngestionSerializer(serializers.Serializer):
    version_label = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    page_count = serializers.IntegerField(read_only=True, allow_null=True)


class StaffDocumentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "title", "slug", "abstract", "language_code", "publication_year",
            "academic_domain", "document_type", "owner_organization",
            "category", "access_model", "confidentiality_notes",
        ]
        # `publication_status` est délibérément absent : l'état n'avance que
        # par les transitions dédiées, qui sont auditées. L'exposer ici
        # contournerait le workflow.


def serialize_rights(document: Document):
    agreement = getattr(document, "rights_agreement", None)
    if agreement is None:
        return None
    return {
        "agreement_type": agreement.agreement_type,
        "rights_holder_name": agreement.rights_holder_name,
        "authorization_status": agreement.authorization_status,
        "withdrawal_rule": agreement.withdrawal_rule,
        "valid_for_publication": agreement.is_valid_for_publication(),
    }


def serialize_ingestion(document: Document):
    from document_ingestion.models import DocumentVersion

    version = (
        DocumentVersion.objects.filter(document=document)
        .order_by("-is_current", "-created_at")
        .first()
    )
    if version is None:
        return None
    return {
        "version_label": version.version_label,
        "status": version.status,
        "page_count": version.page_count,
    }


def serialize_staff_document(document: Document) -> dict:
    authors = (
        DocumentAuthor.objects.filter(document=document)
        .select_related("author")
        .order_by("position", "id")
    )
    return {
        "id": document.pk,
        "slug": document.slug,
        "title": document.title,
        "abstract": document.abstract,
        "language_code": document.language_code,
        "publication_year": document.publication_year,
        "category": document.category,
        "access_model": document.access_model,
        "publication_status": document.publication_status,
        "academic_domain": (
            {"id": document.academic_domain_id, "name": document.academic_domain.name}
            if document.academic_domain_id
            else None
        ),
        "document_type": (
            {"id": document.document_type_id, "name": document.document_type.name}
            if document.document_type_id
            else None
        ),
        "owner_organization": (
            {"id": document.owner_organization_id, "name": document.owner_organization.name}
            if document.owner_organization_id
            else None
        ),
        "authors": [
            {
                "id": entry.author_id,
                "display_name": entry.author.display_name,
                "role": entry.role,
                "position": entry.position,
            }
            for entry in authors
        ],
        "rights": serialize_rights(document),
        "ingestion": serialize_ingestion(document),
        "missing_for_submission": missing_deposit_requirements(document),
        "missing_for_publication": missing_publication_requirements(document),
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "published_at": document.published_at,
    }
