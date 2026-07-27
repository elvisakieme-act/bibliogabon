from __future__ import annotations

from django.conf import settings
from django.db import transaction

from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob
from document_ingestion.storage import storage_key_is_public_reference


def enqueue_processing_job(
    *,
    version: DocumentVersion,
    job_type: str,
    idempotency_key: str,
    source_asset: DocumentAsset | None = None,
    input_payload: dict | None = None,
) -> ProcessingJob:
    job, created = ProcessingJob.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "version": version,
            "source_asset": source_asset,
            "job_type": job_type,
            "input_payload": input_payload or {},
        },
    )
    if not created:
        expected_source_asset_id = source_asset.pk if source_asset else None
        expected_input_payload = input_payload or {}
        if (
            job.version_id != version.pk
            or job.job_type != job_type
            or job.source_asset_id != expected_source_asset_id
            or job.input_payload != expected_input_payload
        ):
            raise ValueError("Idempotency key conflicts with an existing processing job")
    return job


def source_asset_type_for_mime_type(mime_type: str) -> str:
    if mime_type == "application/pdf":
        return DocumentAsset.AssetType.SOURCE_PDF
    if mime_type == "application/epub+zip":
        return DocumentAsset.AssetType.SOURCE_EPUB
    return DocumentAsset.AssetType.SOURCE_RAW


def register_private_upload(
    *,
    document,
    storage_key: str,
    original_filename: str,
    mime_type: str,
    byte_size: int,
    checksum_sha256: str,
    uploaded_by=None,
    version_label: str = "v1",
) -> DocumentAsset:
    if storage_key_is_public_reference(storage_key):
        raise ValueError("storage_key must be a private object key")

    with transaction.atomic():
        version, _ = DocumentVersion.objects.get_or_create(
            document=document,
            version_label=version_label,
            defaults={"uploaded_by": uploaded_by},
        )
        asset_type = source_asset_type_for_mime_type(mime_type)
        asset, created = DocumentAsset.objects.get_or_create(
            version=version,
            asset_type=asset_type,
            checksum_sha256=checksum_sha256,
            defaults={
                "storage_bucket": settings.DOCUMENT_STORAGE_BUCKET,
                "storage_key": storage_key,
                "mime_type": mime_type,
                "byte_size": byte_size,
            },
        )
        if not created and (
            asset.storage_bucket != settings.DOCUMENT_STORAGE_BUCKET
            or asset.storage_key != storage_key
            or asset.mime_type != mime_type
            or asset.byte_size != byte_size
        ):
            raise ValueError("Upload checksum conflicts with existing asset metadata")
        enqueue_processing_job(
            version=version,
            job_type=ProcessingJob.JobType.INGEST_SOURCE,
            idempotency_key=f"ingest:{document.pk}:{version_label}:{checksum_sha256}",
            source_asset=asset,
            input_payload={"original_filename": original_filename},
        )
        return asset
