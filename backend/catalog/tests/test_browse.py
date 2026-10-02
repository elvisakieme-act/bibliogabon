import pytest
from django.utils import timezone

from catalog.browse import (
    DEFAULT_ORDERING,
    ORDERINGS,
    UnknownOrdering,
    browse_documents,
)
from catalog.models import AcademicDomain, Document, DocumentType


def domaine(slug="droit", name="Droit"):
    domain, _ = AcademicDomain.objects.get_or_create(slug=slug, defaults={"name": name})
    return domain


def type_de_document(slug="these", name="Thèse"):
    document_type, _ = DocumentType.objects.get_or_create(slug=slug, defaults={"name": name})
    return document_type


def document(
    *,
    slug,
    title,
    domain_slug="droit",
    language_code="fr",
    access_model=Document.AccessModel.FREE,
    publication_year=2024,
    published_at=None,
    status=Document.PublicationStatus.PUBLISHED,
    type_slug="these",
):
    return Document.objects.create(
        title=title,
        slug=slug,
        academic_domain=domaine(domain_slug, domain_slug.capitalize()),
        document_type=type_de_document(type_slug, type_slug.capitalize()),
        language_code=language_code,
        access_model=access_model,
        publication_year=publication_year,
        publication_status=status,
        published_at=published_at,
    )


@pytest.mark.django_db
def test_browse_shows_only_what_the_public_may_see():
    """Un brouillon ou un document privé ne paraît pas dans le catalogue.

    C'est la règle que tout le reste suppose : filtrer et ordonner n'a de sens
    que sur un fonds déjà restreint à ce qui est publiable.
    """
    document(slug="publie", title="Publié")
    document(slug="brouillon", title="Brouillon", status=Document.PublicationStatus.DRAFT)
    document(slug="prive", title="Privé", access_model=Document.AccessModel.PRIVATE)

    assert [d.slug for d in browse_documents()] == ["publie"]


@pytest.mark.django_db
def test_browse_filters_on_each_criterion():
    document(slug="droit-fr", title="A", domain_slug="droit", language_code="fr")
    document(slug="droit-en", title="B", domain_slug="droit", language_code="en")
    document(slug="medecine", title="C", domain_slug="medecine")
    document(
        slug="abonnement",
        title="D",
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    document(slug="ancien", title="E", publication_year=1999)
    document(slug="cours", title="F", type_slug="cours")

    assert {d.slug for d in browse_documents(domain="medecine")} == {"medecine"}
    assert {d.slug for d in browse_documents(language="en")} == {"droit-en"}
    assert {d.slug for d in browse_documents(access="subscription")} == {"abonnement"}
    assert {d.slug for d in browse_documents(year=1999)} == {"ancien"}
    assert {d.slug for d in browse_documents(document_type="cours")} == {"cours"}


@pytest.mark.django_db
def test_browse_treats_an_unknown_slug_as_an_empty_shelf():
    """Un slug inconnu ne désigne aucun document : c'est une réponse, pas une faute."""
    document(slug="publie", title="Publié")

    assert list(browse_documents(domain="inexistant")) == []


@pytest.mark.django_db
def test_browse_refuses_an_ordering_it_does_not_offer():
    """Un ordre inconnu est refusé, jamais ignoré.

    Un paramètre silencieusement écarté est exactement ce qui faisait croire que
    le catalogue filtrait alors qu'il renvoyait tout.
    """
    with pytest.raises(UnknownOrdering):
        browse_documents(ordering="-page_count")


@pytest.mark.django_db
def test_browse_orders_by_title_by_default():
    document(slug="b", title="Botanique")
    document(slug="a", title="Anthropologie")

    assert [d.slug for d in browse_documents()] == ["a", "b"]
    assert DEFAULT_ORDERING == "title"


@pytest.mark.django_db
def test_browse_orders_by_publication_date_most_recent_first():
    """L'ordre qui permet à l'accueil de dire « entrés récemment »."""
    maintenant = timezone.now()
    document(slug="ancien", title="Z", published_at=maintenant - timezone.timedelta(days=30))
    document(slug="recent", title="A", published_at=maintenant)

    assert [d.slug for d in browse_documents(ordering="-published_at")] == ["recent", "ancien"]


@pytest.mark.django_db
def test_browse_keeps_an_undated_document_out_of_the_front():
    """Une date absente ne se présente pas comme la plus récente.

    PostgreSQL place les valeurs nulles en tête d'un tri décroissant : sans
    `nulls_last`, un document publié sans date aurait ouvert l'accueil.
    """
    document(slug="date", title="A", published_at=timezone.now())
    document(slug="sans-date", title="B", published_at=None)

    assert [d.slug for d in browse_documents(ordering="-published_at")] == ["date", "sans-date"]


def test_every_ordering_ends_on_a_unique_column():
    """Chaque ordre se termine par l'identifiant.

    C'est la déclaration qui est vérifiée, et non deux requêtes successives :
    PostgreSQL *peut* rendre deux fois la même suite sans l'avoir promise, si
    bien qu'un test qui l'observe passe allègrement sur un tri instable — le
    mien le faisait. Ce qui garantit la stabilité est la présence d'une colonne
    unique en dernière position, et cela se lit.

    L'enjeu n'est pas cosmétique : tout le jeu de démonstration est publié dans
    une seule transaction, donc toutes les dates sont égales. Sans départage,
    une même fiche peut paraître sur deux pages successives, ou sur aucune.
    """
    for nom, champs in ORDERINGS.items():
        assert champs[-1] in ("id", "-id"), nom


@pytest.mark.django_db
def test_browse_orders_by_publication_year():
    document(slug="vieux", title="A", publication_year=2001)
    document(slug="neuf", title="B", publication_year=2024)
    document(slug="sans-annee", title="C", publication_year=None)

    assert [d.slug for d in browse_documents(ordering="-publication_year")] == [
        "neuf",
        "vieux",
        "sans-annee",
    ]


def test_offered_orderings_are_a_closed_list():
    """La liste est fermée : un ordre arbitraire ouvrirait la porte à un tri
    sur un champ que le public n'a pas à connaître."""
    assert set(ORDERINGS) == {"title", "-published_at", "-publication_year"}
