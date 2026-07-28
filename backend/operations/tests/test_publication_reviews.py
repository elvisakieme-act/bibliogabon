import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from catalog.models import Document
from operations.models import AuditLog, PublicationReview
from operations.services import open_publication_review, record_publication_decision
from operations.tests.factories import create_publishable_document, create_user


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


@pytest.mark.django_db
def test_open_publication_review_creates_open_review_and_audit_event():
    actor = create_user(email="review-opener@example.ga", is_staff=True)
    reviewer = create_user(email="reviewer@example.ga", is_staff=True)
    document = create_publishable_document(slug="open-review")

    review = open_publication_review(
        document=document,
        actor=actor,
        reviewer=reviewer,
        internal_notes="Check rights before publication",
    )

    assert review.document == document
    assert review.status == PublicationReview.Status.OPEN
    assert review.opened_by == actor
    assert review.reviewer == reviewer
    assert review.internal_notes == "Check rights before publication"
    assert AuditLog.objects.filter(
        event_type="publication_review_opened",
        target_app="catalog",
        target_model="document",
        target_id=str(document.pk),
    ).exists()


@pytest.mark.django_db
def test_open_publication_review_truncates_audit_summary_for_max_length_title():
    actor = create_user(email="long-title-review-opener@example.ga", is_staff=True)
    document = create_publishable_document(slug="long-title-open-review")
    document.title = "T" * 260
    document.save(update_fields=["title", "updated_at"])

    review = open_publication_review(document=document, actor=actor)

    audit_log = AuditLog.objects.get(
        event_type="publication_review_opened",
        target_id=str(document.pk),
    )
    assert review.status == PublicationReview.Status.OPEN
    assert audit_log.summary.startswith("Publication review opened for ")
    assert len(audit_log.summary) == 240


@pytest.mark.django_db
def test_approving_publication_review_publishes_document_and_records_audit():
    actor = create_user(email="review-approver@example.ga", is_staff=True)
    document = create_publishable_document(slug="approve-review")
    review = open_publication_review(document=document, actor=actor)

    decided = record_publication_decision(
        review=review,
        decision=PublicationReview.Status.APPROVED,
        actor=actor,
        reason="Rights and metadata approved",
    )

    document.refresh_from_db()
    assert decided.status == PublicationReview.Status.APPROVED
    assert decided.decided_by == actor
    assert decided.decision_reason == "Rights and metadata approved"
    assert decided.decided_at is not None
    assert document.publication_status == Document.PublicationStatus.PUBLISHED
    assert document.published_at is not None
    assert AuditLog.objects.filter(event_type="publication_review_approved", target_id=str(document.pk)).exists()


@pytest.mark.django_db
def test_publication_decision_truncates_audit_summary_for_max_length_title():
    actor = create_user(email="long-title-review-approver@example.ga", is_staff=True)
    document = create_publishable_document(slug="long-title-approve-review")
    document.title = "T" * 260
    document.save(update_fields=["title", "updated_at"])
    review = PublicationReview.objects.create(document=document, opened_by=actor)

    decided = record_publication_decision(
        review=review,
        decision=PublicationReview.Status.APPROVED,
        actor=actor,
        reason="Rights and metadata approved",
    )

    audit_log = AuditLog.objects.get(
        event_type="publication_review_approved",
        target_id=str(document.pk),
    )
    assert decided.status == PublicationReview.Status.APPROVED
    assert audit_log.summary.startswith("Publication review approved for ")
    assert len(audit_log.summary) == 240


@pytest.mark.django_db
def test_rejecting_publication_review_rejects_document_and_records_audit():
    actor = create_user(email="review-rejecter@example.ga", is_staff=True)
    document = create_publishable_document(slug="reject-review")
    review = open_publication_review(document=document, actor=actor)

    decided = record_publication_decision(
        review=review,
        decision=PublicationReview.Status.REJECTED,
        actor=actor,
        reason="Missing required institutional approval",
    )

    document.refresh_from_db()
    assert decided.status == PublicationReview.Status.REJECTED
    assert document.publication_status == Document.PublicationStatus.REJECTED
    assert document.published_at is None
    assert AuditLog.objects.filter(event_type="publication_review_rejected", target_id=str(document.pk)).exists()


@pytest.mark.django_db
def test_approval_rejects_document_that_is_not_publishable():
    actor = create_user(email="not-publishable-reviewer@example.ga", is_staff=True)
    document = create_publishable_document(slug="not-publishable-review")
    document.academic_domain = None
    document.save(update_fields=["academic_domain", "updated_at"])
    review = open_publication_review(document=document, actor=actor)

    with pytest.raises(ValueError):
        record_publication_decision(
            review=review,
            decision=PublicationReview.Status.APPROVED,
            actor=actor,
            reason="Attempted approval",
        )
