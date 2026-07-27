from __future__ import annotations

from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob


def enqueue_processing_job(
    *,
    version: DocumentVersion,
    job_type: str,
    idempotency_key: str,
    source_asset: DocumentAsset | None = None,
    input_payload: dict | None = None,
) -> ProcessingJob:
    job, _ = ProcessingJob.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "version": version,
            "source_asset": source_asset,
            "job_type": job_type,
            "input_payload": input_payload or {},
        },
    )
    return job
