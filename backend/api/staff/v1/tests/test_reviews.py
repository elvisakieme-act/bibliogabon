"""File de revue de publication.

Le domaine existait déjà et était testé ; rien ne l'atteignait depuis
l'extérieur d'un shell Python. Ces tests couvrent la surface : qui voit la
file, qui décide, et ce que le serveur refuse.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import (
    AcademicDomain,
    Author,
    Document,
    DocumentAuthor,
    DocumentType,
    RightsAgreement,
)
from operations.models import AuditLog, PublicationReview
from operations.services import open_publication_review


def make_user(email: str, account_type: str) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type
    )


@pytest.fixture
def teacher(db):
    return make_user("enseignant-revue@example.ga", User.AccountType.TEACHER_AUTHOR)


@pytest.fixture
def moderator(db):
    return make_user("moderateur-revue@bibliogabon.ga", User.AccountType.CONTENT_ADMIN)


@pytest.fixture
def api():
    return APIClient()


def make_document(
    *,
    slug: str,
    author_user=None,
    rights_approved: bool = True,
    status: str = Document.PublicationStatus.SUBMITTED,
) -> Document:
    domain = AcademicDomain.objects.create(name=f"D {slug}", slug=f"d-{slug}")
    document_type = DocumentType.objects.create(name=f"T {slug}", slug=f"t-{slug}")
    document = Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=status,
    )
    author = Author.objects.create(display_name="Auteur du document", linked_user=author_user)
    DocumentAuthor.objects.create(
        document=document, author=author, role=DocumentAuthor.Role.AUTHOR, position=1
    )
    RightsAgreement.objects.create(
        document=document,
        rights_holder_name="Titulaire",
        agreement_type=RightsAgreement.AgreementType.OPEN_LICENSE,
        authorization_status=(
            RightsAgreement.AuthorizationStatus.APPROVED
            if rights_approved
            else RightsAgreement.AuthorizationStatus.PENDING_REVIEW
        ),
        authorization_date=timezone.now().date() if rights_approved else None,
        access_model=document.access_model,
        withdrawal_rule=RightsAgreement.WithdrawalRule.LICENSE_INVALID,
        reviewer_decision="Approuvé" if rights_approved else "",
        audit_reference=f"audit-{slug}" if rights_approved else "",
    )
    return document


# --- Qui peut voir et agir -------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path_name",
    ["api-staff-v1:review-list"],
)
def test_a_teacher_is_refused_on_the_queue(api, teacher, path_name):
    """La file est la seule liste du back-office qui n'est pas cadrée par la
    paternité — un relecteur doit voir ce que d'autres ont déposé. Elle est
    donc cadrée par le rôle, et fermée à un enseignant."""
    api.force_authenticate(user=teacher)

    assert api.get(reverse(path_name)).status_code == 403


@pytest.mark.django_db
def test_a_teacher_is_refused_on_a_decision(api, teacher, moderator):
    document = make_document(slug="revue-refus-enseignant")
    review = open_publication_review(document=document, actor=moderator)
    api.force_authenticate(user=teacher)

    response = api.post(
        reverse("api-staff-v1:review-decision", kwargs={"review_id": review.pk}),
        {"decision": "approved", "reason": "Peu importe."},
        format="json",
    )

    assert response.status_code == 403
    review.refresh_from_db()
    assert review.status == PublicationReview.Status.OPEN


@pytest.mark.django_db
def test_an_anonymous_visitor_is_refused(api):
    assert api.get(reverse("api-staff-v1:review-list")).status_code in {401, 403}


@pytest.mark.django_db
def test_a_content_admin_who_authored_the_document_cannot_decide_on_it(api, moderator):
    """La séparation des pouvoirs ne doit pas tenir à l'attribution des rôles.
    Un modérateur qui est aussi auteur ne se relit pas lui-même."""
    document = make_document(slug="revue-auteur-moderateur", author_user=moderator)
    review = open_publication_review(document=document, actor=moderator)
    api.force_authenticate(user=moderator)

    response = api.post(
        reverse("api-staff-v1:review-decision", kwargs={"review_id": review.pk}),
        {"decision": "approved", "reason": "Je me relis moi-même."},
        format="json",
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "self_review_forbidden"
    review.refresh_from_db()
    assert review.status == PublicationReview.Status.OPEN


# --- La file ---------------------------------------------------------------


@pytest.mark.django_db
def test_the_queue_lists_open_reviews_with_what_still_blocks_publication(api, moderator):
    """Un relecteur doit voir avant d'ouvrir un dossier que ses droits ne sont
    pas approuvés."""
    blocked = make_document(slug="revue-bloquee", rights_approved=False)
    ready = make_document(slug="revue-prete")
    open_publication_review(document=blocked, actor=moderator)
    open_publication_review(document=ready, actor=moderator)
    api.force_authenticate(user=moderator)

    payload = api.get(reverse("api-staff-v1:review-list")).json()

    by_slug = {row["document"]["slug"]: row for row in payload["results"]}
    assert by_slug["revue-bloquee"]["document"]["missing_for_publication"]
    assert by_slug["revue-prete"]["document"]["missing_for_publication"] == []


@pytest.mark.django_db
def test_the_queue_filters_by_status_and_by_assignment(api, moderator):
    mine = make_document(slug="revue-a-moi")
    other = make_document(slug="revue-a-personne")
    assigned = open_publication_review(document=mine, actor=moderator, reviewer=moderator)
    open_publication_review(document=other, actor=moderator)
    api.force_authenticate(user=moderator)

    unassigned = api.get(reverse("api-staff-v1:review-list"), {"assigned": "none"}).json()
    assert [row["document"]["slug"] for row in unassigned["results"]] == ["revue-a-personne"]

    to_me = api.get(reverse("api-staff-v1:review-list"), {"assigned": "me"}).json()
    assert [row["id"] for row in to_me["results"]] == [assigned.pk]

    closed = api.get(reverse("api-staff-v1:review-list"), {"status": "approved"}).json()
    assert closed["results"] == []


@pytest.mark.django_db
def test_opening_a_review_on_a_document_that_is_not_submitted_is_refused(api, moderator):
    """Une revue sur un brouillon relirait un dossier que son auteur n'a pas
    fini de constituer."""
    draft = make_document(slug="revue-brouillon", status=Document.PublicationStatus.DRAFT)
    api.force_authenticate(user=moderator)

    response = api.post(
        reverse("api-staff-v1:review-list"), {"document": draft.pk}, format="json"
    )

    assert response.status_code == 409
    assert PublicationReview.objects.count() == 0


@pytest.mark.django_db
def test_opening_a_review_twice_returns_the_same_one(api, moderator):
    document = make_document(slug="revue-idempotente")
    api.force_authenticate(user=moderator)

    first = api.post(
        reverse("api-staff-v1:review-list"), {"document": document.pk}, format="json"
    )
    second = api.post(
        reverse("api-staff-v1:review-list"), {"document": document.pk}, format="json"
    )

    assert first.json()["id"] == second.json()["id"]
    assert PublicationReview.objects.count() == 1


@pytest.mark.django_db
def test_assigning_records_the_reviewer(api, moderator):
    document = make_document(slug="revue-assignation")
    review = open_publication_review(document=document, actor=moderator)
    api.force_authenticate(user=moderator)

    response = api.post(
        reverse("api-staff-v1:review-assign", kwargs={"review_id": review.pk}),
        {},
        format="json",
    )

    assert response.status_code == 200
    review.refresh_from_db()
    assert review.reviewer == moderator


# --- La décision -----------------------------------------------------------


@pytest.mark.django_db
def test_approving_publishes_the_document_and_closes_the_review(api, moderator):
    document = make_document(slug="revue-approbation")
    review = open_publication_review(document=document, actor=moderator)
    api.force_authenticate(user=moderator)

    response = api.post(
        reverse("api-staff-v1:review-decision", kwargs={"review_id": review.pk}),
        {"decision": "approved", "reason": "Droits vérifiés, contenu conforme."},
        format="json",
    )

    assert response.status_code == 200
    review.refresh_from_db()
    document.refresh_from_db()
    assert review.status == PublicationReview.Status.APPROVED
    assert review.decided_by == moderator
    assert document.publication_status == Document.PublicationStatus.PUBLISHED


@pytest.mark.django_db
def test_approving_a_document_with_unapproved_rights_is_refused(api, moderator):
    """La barrière des droits vit dans `RightsAgreement.authorization_status`
    depuis D014. L'endpoint doit la faire respecter, pas seulement le service."""
    document = make_document(slug="revue-droits-absents", rights_approved=False)
    review = open_publication_review(document=document, actor=moderator)
    api.force_authenticate(user=moderator)

    response = api.post(
        reverse("api-staff-v1:review-decision", kwargs={"review_id": review.pk}),
        {"decision": "approved", "reason": "Allons-y quand même."},
        format="json",
    )

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "document_not_publishable"
    # Le relecteur doit savoir ce qui bloque, pas seulement que ça bloque.
    assert "rights_agreement_not_approved" in str(body)
    document.refresh_from_db()
    assert document.publication_status == Document.PublicationStatus.SUBMITTED


@pytest.mark.django_db
def test_a_rejection_without_a_reason_is_refused_on_the_right_field(api, moderator):
    document = make_document(slug="revue-rejet-sans-motif")
    review = open_publication_review(document=document, actor=moderator)
    api.force_authenticate(user=moderator)

    response = api.post(
        reverse("api-staff-v1:review-decision", kwargs={"review_id": review.pk}),
        {"decision": "rejected", "reason": "   "},
        format="json",
    )

    assert response.status_code == 400
    assert "reason" in response.json()["error"]["field_errors"]
    review.refresh_from_db()
    assert review.status == PublicationReview.Status.OPEN


@pytest.mark.django_db
def test_rejecting_records_the_reason_and_moves_the_document(api, moderator):
    document = make_document(slug="revue-rejet")
    review = open_publication_review(document=document, actor=moderator)
    api.force_authenticate(user=moderator)

    api.post(
        reverse("api-staff-v1:review-decision", kwargs={"review_id": review.pk}),
        {"decision": "rejected", "reason": "Le consentement de l'étudiant manque."},
        format="json",
    )

    review.refresh_from_db()
    document.refresh_from_db()
    assert review.status == PublicationReview.Status.REJECTED
    assert "consentement" in review.decision_reason
    assert document.publication_status == Document.PublicationStatus.REJECTED


@pytest.mark.django_db
def test_deciding_twice_is_refused(api, moderator):
    document = make_document(slug="revue-double-decision")
    review = open_publication_review(document=document, actor=moderator)
    api.force_authenticate(user=moderator)
    path = reverse("api-staff-v1:review-decision", kwargs={"review_id": review.pk})

    api.post(path, {"decision": "approved", "reason": "Conforme."}, format="json")
    second = api.post(
        path, {"decision": "rejected", "reason": "Finalement non."}, format="json"
    )

    assert second.status_code == 409
    review.refresh_from_db()
    assert review.status == PublicationReview.Status.APPROVED


@pytest.mark.django_db
def test_each_decision_writes_exactly_one_audit_event(api, moderator):
    document = make_document(slug="revue-audit")
    review = open_publication_review(document=document, actor=moderator)
    before = AuditLog.objects.count()
    api.force_authenticate(user=moderator)

    api.post(
        reverse("api-staff-v1:review-decision", kwargs={"review_id": review.pk}),
        {"decision": "approved", "reason": "Conforme."},
        format="json",
    )

    assert AuditLog.objects.count() == before + 1
    event = AuditLog.objects.order_by("-created_at").first()
    assert event.event_type == "publication_review_approved"
    assert event.actor == moderator


@pytest.mark.django_db
def test_an_unknown_decision_is_refused_rather_than_crashing(api, moderator):
    document = make_document(slug="revue-decision-inconnue")
    review = open_publication_review(document=document, actor=moderator)
    api.force_authenticate(user=moderator)

    response = api.post(
        reverse("api-staff-v1:review-decision", kwargs={"review_id": review.pk}),
        {"decision": "peut_etre", "reason": "Hésitation."},
        format="json",
    )

    assert response.status_code == 400
    assert "decision" in response.json()["error"]["field_errors"]


@pytest.mark.django_db
def test_no_review_payload_names_a_stored_object(api, moderator):
    import re

    document = make_document(slug="revue-confidentialite")
    review = open_publication_review(document=document, actor=moderator)
    api.force_authenticate(user=moderator)

    for path in (
        reverse("api-staff-v1:review-list"),
        reverse("api-staff-v1:review-detail", kwargs={"review_id": review.pk}),
    ):
        body = api.get(path).content.decode()
        assert not re.search(r"\.pdf|://|storage|bucket", body, re.I), path
