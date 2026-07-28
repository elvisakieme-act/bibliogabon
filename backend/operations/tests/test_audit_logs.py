import pytest
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError

from operations.models import AuditLog
from operations.services import record_audit_event
from operations.tests.factories import create_publishable_document, create_user


@pytest.mark.django_db
def test_record_audit_event_stores_actor_target_summary_and_metadata():
    actor = create_user(email="audit-service-actor@example.ga", is_staff=True)
    document = create_publishable_document(slug="audit-target")

    log = record_audit_event(
        actor=actor,
        event_type="publication_review_opened",
        target=document,
        summary="Publication review opened",
        metadata={"document_status": document.publication_status},
    )

    assert log.actor == actor
    assert log.event_type == "publication_review_opened"
    assert log.target_app == "catalog"
    assert log.target_model == "document"
    assert log.target_id == str(document.pk)
    assert log.summary == "Publication review opened"
    assert log.metadata == {"document_status": document.publication_status}


@pytest.mark.django_db
def test_record_audit_event_supports_system_event_without_target():
    log = record_audit_event(
        event_type="system_event",
        summary="Nightly maintenance completed",
        metadata={"job": "maintenance"},
    )

    assert log.actor is None
    assert log.target_app == ""
    assert log.target_model == ""
    assert log.target_id == ""
    assert log.metadata == {"job": "maintenance"}


@pytest.mark.django_db
def test_record_audit_event_rejects_unsaved_target():
    document = create_publishable_document(slug="unsaved-audit-target")
    document.pk = None

    with pytest.raises(ValueError, match="target must be saved"):
        record_audit_event(
            event_type="publication_review_opened",
            summary="Publication review opened",
            target=document,
        )


@pytest.mark.parametrize("metadata", [[], False, 0])
@pytest.mark.django_db
def test_record_audit_event_rejects_invalid_metadata(metadata):
    with pytest.raises(ValidationError):
        record_audit_event(
            event_type="system_event",
            summary="Invalid metadata",
            metadata=metadata,
        )


@pytest.mark.django_db
def test_audit_logs_are_immutable_after_creation():
    log = record_audit_event(event_type="system_event", summary="Created")
    log.summary = "Changed"

    with pytest.raises(ValueError):
        log.save()

    assert AuditLog.objects.get(pk=log.pk).summary == "Created"


@pytest.mark.django_db
def test_audit_log_requires_event_type_summary_and_dict_metadata():
    actor = create_user(email="audit-actor@example.ga", is_staff=True)
    log = AuditLog(actor=actor, event_type="", summary="", metadata=[])

    with pytest.raises(ValidationError):
        log.full_clean()


@pytest.mark.django_db
def test_audit_log_cannot_be_deleted_through_an_instance():
    log = AuditLog.objects.create(event_type="document.reviewed", summary="Document reviewed")

    with pytest.raises(ValueError, match="Audit logs are immutable"):
        log.delete()

    assert AuditLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_audit_log_cannot_be_deleted_through_a_queryset():
    log = AuditLog.objects.create(event_type="document.reviewed", summary="Document reviewed")

    with pytest.raises(ValueError, match="Audit logs are immutable"):
        AuditLog.objects.filter(pk=log.pk).delete()

    assert AuditLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_audit_log_cannot_be_deleted_through_the_base_manager():
    log = AuditLog.objects.create(event_type="document.reviewed", summary="Document reviewed")

    with pytest.raises(ValueError, match="Audit logs are immutable"):
        AuditLog._base_manager.filter(pk=log.pk).delete()

    assert AuditLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_audit_log_cannot_be_updated_through_a_queryset():
    log = AuditLog.objects.create(event_type="document.reviewed", summary="Document reviewed")

    with pytest.raises(ValueError, match="Audit logs are immutable"):
        AuditLog.objects.filter(pk=log.pk).update(summary="Changed")

    assert AuditLog.objects.get(pk=log.pk).summary == "Document reviewed"


@pytest.mark.django_db
def test_audit_log_cannot_be_updated_through_the_base_manager():
    log = AuditLog.objects.create(event_type="document.reviewed", summary="Document reviewed")

    with pytest.raises(ValueError, match="Audit logs are immutable"):
        AuditLog._base_manager.filter(pk=log.pk).update(summary="Changed")

    assert AuditLog.objects.get(pk=log.pk).summary == "Document reviewed"


@pytest.mark.django_db
def test_audit_log_cannot_be_bulk_updated():
    log = AuditLog.objects.create(event_type="document.reviewed", summary="Document reviewed")
    log.summary = "Changed"

    with pytest.raises(ValueError, match="Audit logs are immutable"):
        AuditLog.objects.bulk_update([log], ["summary"])

    assert AuditLog.objects.get(pk=log.pk).summary == "Document reviewed"


@pytest.mark.django_db
def test_audit_log_actor_is_protected_from_deletion():
    actor = create_user(email="protected-audit-actor@example.ga")
    log = AuditLog.objects.create(
        actor=actor,
        event_type="document.reviewed",
        summary="Document reviewed",
    )

    with pytest.raises(ProtectedError):
        actor.delete()

    assert AuditLog.objects.get(pk=log.pk).actor == actor
