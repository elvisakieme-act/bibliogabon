"""Tâches Celery du pilier d'ingestion.

Chaque tâche reçoit un identifiant, jamais une instance : elle recharge sa
ligne, ce qui la rend rejouable telle quelle après la mort d'un worker. La
logique métier reste dans `pipeline.process_ingest_job` ; la tâche n'est
qu'une enveloppe qui gère l'état du job et les réessais.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

from document_ingestion.models import ProcessingJob
from document_ingestion.pipeline import process_ingest_job


logger = logging.getLogger(__name__)

MAX_RETRIES = 3
# Backoff exponentiel borne : 30 s, 60 s, 120 s. Un PDF illisible ne doit pas
# monopoliser un worker, mais une panne passagere de stockage doit avoir le
# temps de se resorber.
RETRY_BASE_DELAY_SECONDS = 30
RETRY_MAX_DELAY_SECONDS = 600


def runs_inline() -> bool:
    """Vrai quand les tâches s'exécutent sans broker.

    Dans ce mode, Celery ne réexécute pas une tâche : reprogrammer un essai
    masquerait l'erreur d'origine derrière une exception `Retry`. On laisse
    donc remonter l'échec réel.
    """
    return bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False))


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def ingest_source_document(self, job_id: int) -> int:
    job = ProcessingJob.objects.get(pk=job_id)

    if job.status == ProcessingJob.Status.SUCCEEDED:
        logger.info("Job d'ingestion %s deja termine : rien a rejouer.", job_id)
        return job.version_id

    attempt = self.request.retries or 0
    job.celery_task_id = self.request.id or ""
    job.retry_count = attempt
    job.save(update_fields=["celery_task_id", "retry_count", "updated_at"])

    try:
        version = process_ingest_job(job)
    except Exception as exc:
        job.refresh_from_db()
        if runs_inline() or attempt >= MAX_RETRIES:
            job.mark_failed(
                error_code=job.error_code or "ingest_failed",
                message=job.error_message or str(exc),
                retry_count=attempt,
            )
            raise
        job.mark_retrying(
            error_code=job.error_code or "ingest_failed",
            message=job.error_message or str(exc),
            retry_count=attempt,
        )
        countdown = min(
            RETRY_BASE_DELAY_SECONDS * (2**attempt), RETRY_MAX_DELAY_SECONDS
        )
        raise self.retry(exc=exc, countdown=countdown)

    return version.pk
