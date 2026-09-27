"""Dépôt du fichier source.

Seul mécanisme réellement neuf de la tranche. Trois exigences le
gouvernent :

- le fichier ne transite jamais entièrement en mémoire — au-delà de
  `FILE_UPLOAD_MAX_MEMORY_SIZE`, Django le déverse dans un fichier
  temporaire, et `ingest_document_file` le lit en flux ;
- les bornes sont vérifiées **avant** d'écrire quoi que ce soit, pour
  qu'un refus ne laisse rien en stockage ;
- la réponse ne dit rien du chemin de stockage. Le fichier entre ;
  rien n'en ressort.
"""

from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from accounts import permissions as roles
from api.staff.v1.documents import get_visible_document
from api.staff.v1.serializers import serialize_staff_document
from api.staff.v1.views import StaffAPIView
from api.v1.errors import error_response
from catalog.models import Document
from document_ingestion.exceptions import VersionAlreadyIngested
from document_ingestion.models import DocumentVersion, ProcessingJob
from document_ingestion.pipeline import ingest_document_file
from operations.services import record_audit_event

# États dans lesquels un déposant peut encore remplacer sa source. Au-delà,
# le contenu diffusé a été validé : la correction repasse par un modérateur.
DEPOSITOR_EDITABLE_STATES = frozenset(
    {Document.PublicationStatus.DRAFT, Document.PublicationStatus.SUBMITTED}
)


class DocumentSourceView(StaffAPIView):
    # Exception délibérée à la règle « JSON uniquement » du contrat public :
    # un fichier ne voyage pas en JSON sans que le base64 l'alourdisse d'un
    # tiers, et sans le charger entièrement en mémoire pour l'encoder.
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=["Staff deposit"],
        summary="Upload the source file of a document",
        description=(
            "multipart/form-data. The file is stored privately and ingestion is "
            "queued. The response reports the resulting version and never a "
            "storage key, path or URL."
        ),
        operation_id="staff_v1_document_source_upload",
        parameters=[
            OpenApiParameter(
                "replace",
                bool,
                description="Replace the content of an already ingested version.",
            )
        ],
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
            }
        },
    )
    def post(self, request, document_id: int):
        if not roles.can_submit_document(request.user):
            return error_response(
                "permission_denied", "Vous ne pouvez pas déposer de fichier.", 403
            )

        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        if (
            document.publication_status not in DEPOSITOR_EDITABLE_STATES
            and not roles.can_review_publication(request.user)
        ):
            return error_response(
                "document_locked",
                "Ce document a dépassé le stade du dépôt ; seul un modérateur "
                "peut en remplacer la source.",
                409,
            )

        upload = request.FILES.get("file")
        if upload is None:
            return error_response(
                "invalid_request",
                "Aucun fichier reçu.",
                400,
                {"file": ["Ce champ est obligatoire."]},
            )

        # Bornes d'abord : un refus ne doit rien écrire.
        max_bytes = int(getattr(settings, "DOCUMENT_UPLOAD_MAX_BYTES", 200 * 1024 * 1024))
        if upload.size > max_bytes:
            return error_response(
                "file_too_large",
                f"Le fichier dépasse la taille maximale de {max_bytes} octets.",
                413,
            )

        accepted = set(getattr(settings, "DOCUMENT_UPLOAD_ACCEPTED_MIME_TYPES", []))
        if accepted and upload.content_type not in accepted:
            return error_response(
                "unsupported_media_type",
                f"Type de fichier non accepté : {upload.content_type}.",
                415,
            )

        try:
            version = ingest_document_file(
                document=document,
                fileobj=upload,
                original_filename=upload.name,
                mime_type=upload.content_type,
                uploaded_by=request.user,
                replace=request.query_params.get("replace") == "true",
            )
        except VersionAlreadyIngested as exc:
            return error_response(
                "version_already_ingested",
                str(exc),
                409,
                {"version_label": [exc.version_label]},
            )

        record_audit_event(
            actor=request.user,
            event_type="document_source_uploaded",
            target=document,
            summary=f"Fichier source déposé pour « {document.title} »",
            metadata={
                "document_id": document.pk,
                "version_label": version.version_label,
                "byte_size": upload.size,
            },
        )

        document.refresh_from_db()
        return Response(serialize_staff_document(document), status=status.HTTP_201_CREATED)


# --- Suivi du traitement -----------------------------------------------------

# États agrégés, pour que l'écran n'ait pas à recombiner ceux de la version et
# du job. Un écran qui devrait les croiser lui-même finirait par afficher
# « terminé » sur un travail en cours.
STATE_NO_SOURCE = "no_source"
STATE_IN_PROGRESS = "in_progress"
STATE_READY = "ready"
STATE_FAILED = "failed"


def _aggregate_state(version, job) -> str:
    if version is None:
        return STATE_NO_SOURCE
    if version.status == DocumentVersion.Status.FAILED or (
        job is not None and job.status == ProcessingJob.Status.FAILED
    ):
        return STATE_FAILED
    if version.status == DocumentVersion.Status.PROCESSED:
        return STATE_READY
    return STATE_IN_PROGRESS


class DocumentIngestionView(StaffAPIView):
    @extend_schema(
        tags=["Staff deposit"],
        summary="Report the ingestion state of a document",
        description=(
            "Version state, page count, job state, retry count and failure "
            "reason. A document with no source reports no_source rather than "
            "404 — it exists, it has simply received nothing yet. Never "
            "exposes a storage key."
        ),
        operation_id="staff_v1_document_ingestion_status",
    )
    def get(self, request, document_id: int):
        document = get_visible_document(request.user, document_id)
        if document is None:
            return error_response("not_found", "Document introuvable.", 404)

        version = (
            DocumentVersion.objects.filter(document=document)
            .order_by("-is_current", "-created_at")
            .first()
        )
        job = (
            ProcessingJob.objects.filter(version=version).order_by("-created_at").first()
            if version is not None
            else None
        )

        return Response(
            {
                "state": _aggregate_state(version, job),
                "version": (
                    {
                        "version_label": version.version_label,
                        "status": version.status,
                        "is_current": version.is_current,
                        "page_count": version.page_count,
                        "processed_at": version.processed_at,
                    }
                    if version is not None
                    else None
                ),
                "job": (
                    {
                        "status": job.status,
                        "retry_count": job.retry_count,
                        "error_code": job.error_code,
                        "error_message": job.error_message,
                        "started_at": job.started_at,
                        "completed_at": job.completed_at,
                    }
                    if job is not None
                    else None
                ),
            }
        )
