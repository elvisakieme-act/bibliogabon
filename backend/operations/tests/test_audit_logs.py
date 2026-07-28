import pytest
from django.core.exceptions import ValidationError

from operations.models import AuditLog
from operations.tests.factories import create_user


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
