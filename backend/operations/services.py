from __future__ import annotations

from django.db import transaction

from operations.models import AuditLog


def _target_parts(target) -> tuple[str, str, str]:
    if target is None:
        return "", "", ""
    if target._state.adding or target.pk is None:
        raise ValueError("target must be saved")
    meta = target._meta
    return meta.app_label, meta.model_name, str(target.pk)


def record_audit_event(
    *,
    event_type: str,
    summary: str,
    actor=None,
    target=None,
    metadata: dict | None = None,
) -> AuditLog:
    target_app, target_model, target_id = _target_parts(target)
    with transaction.atomic():
        return AuditLog.objects.create(
            actor=actor,
            event_type=event_type,
            target_app=target_app,
            target_model=target_model,
            target_id=target_id,
            summary=summary,
            metadata=metadata if metadata is not None else {},
        )
