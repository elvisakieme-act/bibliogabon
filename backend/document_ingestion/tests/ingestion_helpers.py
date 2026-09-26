"""Aides de test partagées pour l'ingestion.

Ce module n'est pas collecté par pytest (son nom ne commence pas par
`test_`) : il fournit une ingestion « source seule », sans le travail par
page, pour les tests qui veulent déclencher l'OCR ou l'indexation
eux-mêmes et observer l'état intermédiaire.
"""

from __future__ import annotations

import hashlib
import io

from document_ingestion.blob_storage import save_stream
from document_ingestion.models import ProcessingJob
from document_ingestion.pipeline import process_ingest_job
from document_ingestion.services import register_private_upload
from document_ingestion.storage import build_private_storage_key


def ingest_source_only(document, payload: bytes, *, version_label: str = "v1"):
    """Découpe le PDF et extrait sa couche texte, sans OCR, sans rendu
    d'image et sans consommer la file d'index."""
    checksum = hashlib.sha256(payload).hexdigest()
    storage_key = build_private_storage_key(
        document=document,
        version_label=version_label,
        original_filename="source.pdf",
        checksum_sha256=checksum,
    )
    save_stream(storage_key, io.BytesIO(payload))
    register_private_upload(
        document=document,
        storage_key=storage_key,
        original_filename="source.pdf",
        mime_type="application/pdf",
        byte_size=len(payload),
        checksum_sha256=checksum,
        version_label=version_label,
    )
    job = ProcessingJob.objects.get(
        idempotency_key=f"ingest:{document.pk}:{version_label}:{checksum}"
    )
    return process_ingest_job(job)
