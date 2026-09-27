from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser

from accounts.models import User
from api.staff.v1.scoping import documents_visible_to
from catalog.models import AcademicDomain, Author, Document, DocumentAuthor


def make_user(email: str, account_type: str) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type
    )


def make_document(*, slug: str, status: str, access_model: str, author: User | None = None):
    domain, _ = AcademicDomain.objects.get_or_create(name="Droit", slug="droit")
    document = Document.objects.create(
        title=slug,
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=status,
    )
    if author is not None:
        entry = Author.objects.create(
            display_name=author.email, normalized_name=author.email, linked_user=author
        )
        DocumentAuthor.objects.create(
            document=document, author=entry, role=DocumentAuthor.Role.AUTHOR
        )
    return document


@pytest.fixture
def corpus(db):
    teacher = make_user("enseignant@example.ga", User.AccountType.TEACHER_AUTHOR)
    other = make_user("autre@example.ga", User.AccountType.TEACHER_AUTHOR)
    return {
        "teacher": teacher,
        "other": other,
        "student": make_user("etudiant@example.ga", User.AccountType.INDIVIDUAL),
        "content_admin": make_user("mod@bibliogabon.ga", User.AccountType.CONTENT_ADMIN),
        "draft_mine": make_document(
            slug="brouillon-a-moi",
            status=Document.PublicationStatus.DRAFT,
            access_model=Document.AccessModel.FREE,
            author=teacher,
        ),
        "private_mine": make_document(
            slug="prive-a-moi",
            status=Document.PublicationStatus.TECHNICAL_PROCESSING,
            access_model=Document.AccessModel.PRIVATE,
            author=teacher,
        ),
        "published_mine": make_document(
            slug="publie-a-moi",
            status=Document.PublicationStatus.PUBLISHED,
            access_model=Document.AccessModel.FREE,
            author=teacher,
        ),
        "draft_theirs": make_document(
            slug="brouillon-dautrui",
            status=Document.PublicationStatus.DRAFT,
            access_model=Document.AccessModel.FREE,
            author=other,
        ),
        "orphan": make_document(
            slug="sans-auteur",
            status=Document.PublicationStatus.DRAFT,
            access_model=Document.AccessModel.FREE,
        ),
    }


def slugs(queryset) -> set[str]:
    return set(queryset.values_list("slug", flat=True))


def test_a_content_admin_sees_every_state_including_draft_and_private(corpus):
    visible = slugs(documents_visible_to(corpus["content_admin"]))

    assert visible == {
        "brouillon-a-moi",
        "prive-a-moi",
        "publie-a-moi",
        "brouillon-dautrui",
        "sans-auteur",
    }


def test_a_teacher_sees_only_what_they_authored_in_any_state(corpus):
    visible = slugs(documents_visible_to(corpus["teacher"]))

    assert visible == {"brouillon-a-moi", "prive-a-moi", "publie-a-moi"}


def test_a_teacher_sees_nothing_authored_by_someone_else(corpus):
    visible = slugs(documents_visible_to(corpus["teacher"]))

    assert "brouillon-dautrui" not in visible
    assert "sans-auteur" not in visible


def test_a_student_sees_nothing(corpus):
    assert slugs(documents_visible_to(corpus["student"])) == set()


def test_an_anonymous_caller_sees_nothing(corpus):
    assert slugs(documents_visible_to(AnonymousUser())) == set()


def test_a_teacher_listed_as_coauthor_still_sees_the_document(corpus):
    document = corpus["draft_theirs"]
    entry = Author.objects.create(
        display_name="co", normalized_name="co", linked_user=corpus["teacher"]
    )
    DocumentAuthor.objects.create(
        document=document, author=entry, role=DocumentAuthor.Role.COAUTHOR, position=2
    )

    assert "brouillon-dautrui" in slugs(documents_visible_to(corpus["teacher"]))


def test_the_queryset_has_no_duplicates_when_listed_twice(corpus):
    """Un auteur rattache deux fois ne doit pas dedoubler la ligne."""
    document = corpus["draft_mine"]
    entry = Author.objects.create(
        display_name="bis", normalized_name="bis", linked_user=corpus["teacher"]
    )
    DocumentAuthor.objects.create(
        document=document, author=entry, role=DocumentAuthor.Role.COAUTHOR, position=2
    )

    visible = list(documents_visible_to(corpus["teacher"]).values_list("slug", flat=True))
    assert len(visible) == len(set(visible)), visible


@pytest.mark.django_db
def test_the_public_catalog_is_unaffected_for_the_same_content_admin(corpus, client):
    """La surface staff elargit la visibilite des endpoints staff, pas du
    produit : le catalogue public continue d'exclure brouillons et prives."""
    from django.urls import reverse

    response = client.get(reverse("api-v1:catalog-documents"))

    public = {item["slug"] for item in response.json()["results"]}
    assert public == {"publie-a-moi"}
