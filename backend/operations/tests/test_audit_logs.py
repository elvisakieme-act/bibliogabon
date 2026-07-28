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
