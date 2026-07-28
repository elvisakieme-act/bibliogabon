import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from operations.models import PublicationReview
from operations.tests.factories import create_publishable_document


@pytest.mark.django_db
def test_publication_review_rejected_requires_decision_reason():
    document = create_publishable_document(slug="rejected-requires-reason")
    review = PublicationReview(
        document=document,
        status=PublicationReview.Status.REJECTED,
        decided_at=timezone.now(),
    )

    with pytest.raises(ValidationError):
        review.full_clean()
