from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser

from accounts.models import Organization, OrganizationMembership, User
from accounts.permissions import (
    administered_organization_ids,
    administers_organization,
    can_manage_billing,
    can_manage_organization_members,
    can_review_publication,
    can_submit_document,
    can_view_organization_reports,
    can_withdraw_document,
    is_content_admin,
    is_platform_staff,
)
from catalog.models import AcademicDomain, Author, Document, DocumentAuthor

# --- Les sept acteurs du document produit -----------------------------------


def make_user(email: str, account_type: str, **extra) -> User:
    return User.objects.create_user(
        email=email, password="passphrase", account_type=account_type, **extra
    )


@pytest.fixture
def organization(db) -> Organization:
    return Organization.objects.create(
        name="Universite Omar Bongo",
        slug="uob",
        organization_type=Organization.OrganizationType.UNIVERSITY,
    )


@pytest.fixture
def sponsor(db) -> Organization:
    return Organization.objects.create(
        name="Fondation Lumiere",
        slug="fondation-lumiere",
        organization_type=Organization.OrganizationType.SPONSOR,
    )


@pytest.fixture
def actors(db, organization, sponsor) -> dict[str, object]:
    visitor = AnonymousUser()
    student = make_user("etudiant@example.ga", User.AccountType.INDIVIDUAL)
    teacher = make_user("enseignant@example.ga", User.AccountType.TEACHER_AUTHOR)
    institution_admin = make_user("admin-uob@example.ga", User.AccountType.ORGANIZATION_ADMIN)
    sponsor_partner = make_user("sponsor@example.ga", User.AccountType.ORGANIZATION_ADMIN)
    content_admin = make_user(
        "moderation@bibliogabon.ga", User.AccountType.CONTENT_ADMIN, is_staff=True
    )
    super_admin = User.objects.create_superuser(
        email="root@bibliogabon.ga", password="passphrase"
    )

    for user, org in ((institution_admin, organization), (sponsor_partner, sponsor)):
        OrganizationMembership.objects.create(
            organization=org,
            user=user,
            role=OrganizationMembership.Role.ADMIN,
            status=OrganizationMembership.Status.ACTIVE,
        )

    return {
        "visitor": visitor,
        "student": student,
        "teacher": teacher,
        "institution_admin": institution_admin,
        "sponsor_partner": sponsor_partner,
        "content_admin": content_admin,
        "super_admin": super_admin,
    }


ALL_ACTORS = [
    "visitor",
    "student",
    "teacher",
    "institution_admin",
    "sponsor_partner",
    "content_admin",
    "super_admin",
]


# --- Prédicats non scopés ----------------------------------------------------


@pytest.mark.parametrize(
    ("predicate", "allowed"),
    [
        (is_platform_staff, {"super_admin"}),
        (is_content_admin, {"content_admin", "super_admin"}),
        (can_submit_document, {"teacher", "content_admin", "super_admin"}),
        (can_review_publication, {"content_admin", "super_admin"}),
        (can_manage_billing, {"super_admin"}),
    ],
)
def test_predicate_answers_correctly_for_every_actor(actors, predicate, allowed):
    for name in ALL_ACTORS:
        expected = name in allowed
        assert predicate(actors[name]) is expected, (
            f"{predicate.__name__} pour « {name} » : attendu {expected}"
        )


def test_a_visitor_holds_no_management_capability(actors):
    visitor = actors["visitor"]

    assert can_submit_document(visitor) is False
    assert can_review_publication(visitor) is False
    assert can_manage_billing(visitor) is False
    assert administered_organization_ids(visitor) == []


def test_a_student_holds_no_management_capability(actors, organization):
    student = actors["student"]

    assert can_submit_document(student) is False
    assert can_review_publication(student) is False
    assert can_manage_billing(student) is False
    assert can_manage_organization_members(student, organization) is False


def test_a_content_admin_cannot_manage_billing(actors):
    """Perimetre borne : la moderation de contenu n'ouvre pas la facturation."""
    assert can_review_publication(actors["content_admin"]) is True
    assert can_manage_billing(actors["content_admin"]) is False


# --- Prédicats scopés à une organisation -------------------------------------


def test_only_the_organization_admin_manages_its_members(actors, organization):
    for name in ALL_ACTORS:
        expected = name in {"institution_admin", "super_admin"}
        assert can_manage_organization_members(actors[name], organization) is expected, name


def test_a_sponsor_partner_administers_its_own_sponsor_organization(
    actors, sponsor, organization
):
    """Sponsor Partner n'est pas un type de compte : c'est un admin
    d'organisation dont l'organisation est de type sponsor."""
    partner = actors["sponsor_partner"]

    assert administers_organization(partner, sponsor) is True
    assert can_view_organization_reports(partner, sponsor) is True
    assert administers_organization(partner, organization) is False


def test_administered_organization_ids_lists_only_administered_ones(
    actors, organization, sponsor
):
    assert administered_organization_ids(actors["institution_admin"]) == [organization.pk]
    assert administered_organization_ids(actors["sponsor_partner"]) == [sponsor.pk]
    assert administered_organization_ids(actors["student"]) == []


def test_a_plain_member_does_not_administer_its_organization(db, organization):
    member = make_user("membre@example.ga", User.AccountType.INDIVIDUAL)
    OrganizationMembership.objects.create(
        organization=organization,
        user=member,
        role=OrganizationMembership.Role.MEMBER,
        status=OrganizationMembership.Status.ACTIVE,
    )

    assert administers_organization(member, organization) is False


# --- Retrait d'un document ---------------------------------------------------


def make_document(*, category, owner=None, slug="document") -> Document:
    domain, _ = AcademicDomain.objects.get_or_create(name="Droit", slug="droit")
    document = Document.objects.create(
        title="Document",
        slug=slug,
        academic_domain=domain,
        category=category,
        access_model=Document.AccessModel.FREE,
    )
    if owner is not None:
        author = Author.objects.create(
            display_name=owner.email, normalized_name=owner.email, linked_user=owner
        )
        DocumentAuthor.objects.create(
            document=document, author=author, role=DocumentAuthor.Role.AUTHOR
        )
    return document


def test_a_teacher_may_withdraw_their_own_voluntary_deposit(actors):
    teacher = actors["teacher"]
    document = make_document(
        category=Document.Category.VOLUNTARY_TEACHER_DEPOSIT,
        owner=teacher,
        slug="depot-volontaire",
    )

    assert can_withdraw_document(teacher, document) is True


def test_a_teacher_may_not_withdraw_an_institutional_fund_document(actors):
    """« Les fonds institutionnels suivent les regles du contrat. »"""
    teacher = actors["teacher"]
    document = make_document(
        category=Document.Category.INSTITUTIONAL_FUND,
        owner=teacher,
        slug="fonds-institutionnel",
    )

    assert can_withdraw_document(teacher, document) is False


def test_a_teacher_may_not_withdraw_someone_elses_deposit(actors):
    other = make_user("autre@example.ga", User.AccountType.TEACHER_AUTHOR)
    document = make_document(
        category=Document.Category.VOLUNTARY_TEACHER_DEPOSIT, owner=other, slug="depot-dautrui"
    )

    assert can_withdraw_document(actors["teacher"], document) is False


def test_a_content_admin_may_withdraw_either_kind(actors):
    voluntary = make_document(
        category=Document.Category.VOLUNTARY_TEACHER_DEPOSIT, owner=actors["teacher"], slug="v"
    )
    institutional = make_document(category=Document.Category.INSTITUTIONAL_FUND, slug="i")

    assert can_withdraw_document(actors["content_admin"], voluntary) is True
    assert can_withdraw_document(actors["content_admin"], institutional) is True


def test_an_institution_admin_may_not_withdraw_a_document(actors):
    """« Ne peut pas publier ni retirer un document globalement. »"""
    document = make_document(category=Document.Category.INSTITUTIONAL_FUND, slug="ins")

    assert can_withdraw_document(actors["institution_admin"], document) is False


# --- Les rôles n'ouvrent aucun accès au contenu ------------------------------


def test_a_role_grants_no_reading_access(actors, organization):
    """Identite, role et entitlement restent trois choses distinctes : aucun
    role ne doit ouvrir la lecture d'un document restreint."""
    from document_reader.services import user_can_read_document

    restricted = make_document(category=Document.Category.INSTITUTIONAL_FUND, slug="restreint")
    restricted.access_model = Document.AccessModel.SUBSCRIPTION
    restricted.publication_status = Document.PublicationStatus.PUBLISHED
    restricted.save()

    for name in ("teacher", "institution_admin", "content_admin", "super_admin"):
        assert user_can_read_document(actors[name], restricted) is False, name


def test_contract_bound_categories_match_the_catalog(db):
    """`accounts` ne peut pas importer `catalog` sans inverser la dependance,
    donc les categories sont des litteraux. Ce test les verrouille."""
    from accounts.permissions import CONTRACT_BOUND_CATEGORIES

    assert CONTRACT_BOUND_CATEGORIES <= set(Document.Category.values)
    assert CONTRACT_BOUND_CATEGORIES == {
        Document.Category.INSTITUTIONAL_FUND,
        Document.Category.COMMERCIAL_PARTNER_CONTENT,
    }


def test_a_student_work_stays_withdrawable_by_its_author(actors):
    """« Le retrait peut etre demande par l'etudiant, l'ayant droit ou
    l'etablissement concerne ; la confidentialite prime. »"""
    teacher = actors["teacher"]
    document = make_document(
        category=Document.Category.STUDENT_WORK, owner=teacher, slug="travail-etudiant"
    )

    assert can_withdraw_document(teacher, document) is True
