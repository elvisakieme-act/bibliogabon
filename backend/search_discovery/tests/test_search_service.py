import pytest

from catalog.models import AcademicDomain, Author, Document, DocumentAuthor
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_processing.services import attach_extracted_text, create_page_records
from search_discovery.services import rebuild_document_search_index


def create_document(
    *,
    slug,
    title,
    domain_slug="education",
    domain_name="Education",
    abstract="",
    language_code="fr",
    publication_year=2026,
    access_model=Document.AccessModel.FREE,
):
    domain, _ = AcademicDomain.objects.get_or_create(
        slug=domain_slug,
        defaults={"name": domain_name},
    )
    return Document.objects.create(
        title=title,
        slug=slug,
        abstract=abstract,
        language_code=language_code,
        publication_year=publication_year,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )


def add_author(document, display_name, position=1):
    author = Author.objects.create(
        display_name=display_name,
        normalized_name=display_name.lower(),
    )
    DocumentAuthor.objects.create(document=document, author=author, position=position)
    return author


def add_processed_text(document, text):
    version = DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=1,
    )
    page = create_page_records(version=version, page_count=1)[0]
    page.status = DocumentPage.Status.PROCESSED
    page.save(update_fields=["status", "updated_at"])
    attach_extracted_text(page=page, text=text, language_code=document.language_code)
    return page


@pytest.mark.django_db
def test_search_documents_ranks_title_matches_above_body_only_matches():
    from search_discovery.services import search_documents

    title_match = create_document(slug="pedagogie-title", title="Pedagogie inclusive")
    add_processed_text(title_match, "Texte general sur les politiques universitaires.")
    rebuild_document_search_index(title_match)
    body_match = create_document(slug="pedagogie-body", title="Sante publique")
    add_processed_text(body_match, "La pedagogie dans les lycees techniques.")
    rebuild_document_search_index(body_match)

    results = search_documents(query="pedagogie")

    assert [result["document_id"] for result in results] == [title_match.pk, body_match.pk]
    assert results[0]["score"] > results[1]["score"]
    assert results[0]["text_match"] is False
    assert results[1]["text_match"] is True


@pytest.mark.django_db
def test_search_documents_keeps_title_match_above_combined_lower_priority_matches():
    from search_discovery.services import search_documents

    title_match = create_document(slug="microfinance-title", title="Microfinance rurale")
    rebuild_document_search_index(title_match)
    combined_match = create_document(
        slug="microfinance-combined",
        title="Cooperatives agricoles",
        domain_slug="microfinance-domain",
        domain_name="Microfinance appliquee",
        abstract="Guide pratique de microfinance pour les cooperatives.",
    )
    add_author(combined_match, "Microfinance Gabon")
    add_processed_text(combined_match, "Etude de cas microfinance.")
    rebuild_document_search_index(combined_match)

    results = search_documents(query="microfinance")

    assert [result["document_id"] for result in results] == [title_match.pk, combined_match.pk]
    assert results[0]["score"] > results[1]["score"]


@pytest.mark.django_db
def test_search_documents_matches_author_domain_abstract_and_internal_body_text():
    from search_discovery.services import search_documents

    document = create_document(
        slug="hydrologie-gabon",
        title="Hydrologie du Gabon",
        domain_slug="environnement",
        domain_name="Sciences environnementales",
        abstract="Analyse du bassin de l Ogooue.",
    )
    add_author(document, "Aline NZE")
    add_processed_text(document, "Cartographie des zones humides.")
    rebuild_document_search_index(document)

    assert search_documents(query="NZE")[0]["document_id"] == document.pk
    assert search_documents(query="environnementales")[0]["document_id"] == document.pk
    assert search_documents(query="Ogooue")[0]["document_id"] == document.pk
    body_result = search_documents(query="zones humides")[0]
    assert body_result["document_id"] == document.pk
    assert body_result["text_match"] is True


@pytest.mark.django_db
def test_search_documents_filters_by_domain_language_access_and_publication_year():
    from search_discovery.services import search_documents

    matching = create_document(
        slug="matching-filter",
        title="Archive numerique gabonaise",
        domain_slug="archives",
        domain_name="Archives",
        language_code="fr",
        publication_year=2026,
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    rebuild_document_search_index(matching)
    rebuild_document_search_index(
        create_document(slug="other-domain", title="Autre domaine", domain_slug="droit", domain_name="Droit")
    )
    rebuild_document_search_index(
        create_document(slug="other-language", title="Autre langue", language_code="en")
    )
    rebuild_document_search_index(
        create_document(slug="other-access", title="Autre acces", access_model=Document.AccessModel.FREE)
    )
    rebuild_document_search_index(
        create_document(slug="other-year", title="Autre annee", publication_year=2025)
    )

    results = search_documents(
        domain_slug="archives",
        language_code="fr",
        access_model=Document.AccessModel.SUBSCRIPTION,
        publication_year=2026,
    )

    assert [result["document_id"] for result in results] == [matching.pk]


@pytest.mark.django_db
def test_search_documents_returns_live_access_model_when_index_access_is_stale():
    from search_discovery.services import search_documents

    document = create_document(slug="stale-access", title="Droit public gabonais")
    rebuild_document_search_index(document)
    document.access_model = Document.AccessModel.SUBSCRIPTION
    document.save(update_fields=["access_model", "updated_at"])

    results = search_documents(access_model=Document.AccessModel.SUBSCRIPTION)

    assert len(results) == 1
    assert results[0]["document_id"] == document.pk
    assert results[0]["access_model"] == Document.AccessModel.SUBSCRIPTION


@pytest.mark.parametrize(
    ("publication_status", "access_model"),
    [
        (Document.PublicationStatus.WITHDRAWN, Document.AccessModel.FREE),
        (Document.PublicationStatus.PUBLISHED, Document.AccessModel.PRIVATE),
    ],
)
@pytest.mark.django_db
def test_search_documents_excludes_stale_indexes_for_now_hidden_documents(publication_status, access_model):
    from search_discovery.services import search_documents

    document = create_document(slug=f"stale-hidden-{publication_status}-{access_model}", title="Notice cachee")
    rebuild_document_search_index(document)
    document.publication_status = publication_status
    document.access_model = access_model
    document.save(update_fields=["publication_status", "access_model", "updated_at"])

    assert search_documents(query="Notice") == []


@pytest.mark.django_db
def test_search_documents_empty_query_returns_indexed_records_sorted_by_title():
    from search_discovery.services import search_documents

    second = create_document(slug="z-title", title="Zoologie appliquee")
    first = create_document(slug="a-title", title="Agronomie tropicale")
    rebuild_document_search_index(second)
    rebuild_document_search_index(first)

    results = search_documents()

    assert [result["document_id"] for result in results] == [first.pk, second.pk]
    assert [result["score"] for result in results] == [0, 0]


@pytest.mark.django_db
def test_search_documents_returns_safe_payload_and_enforces_limit():
    from search_discovery.services import search_documents

    first = create_document(slug="safe-payload-a", title="Anthropologie")
    add_author(first, "Brice ONDO")
    add_processed_text(first, "Texte interne protege.")
    rebuild_document_search_index(first)
    second = create_document(slug="safe-payload-b", title="Botanique")
    rebuild_document_search_index(second)

    results = search_documents(limit=1)

    assert len(results) == 1
    payload = results[0]
    assert set(payload) == {
        "document_id",
        "title",
        "slug",
        "abstract",
        "language_code",
        "publication_year",
        "academic_domain",
        "authors",
        "access_model",
        "indexed_page_count",
        "score",
        "text_match",
    }
    assert payload["authors"] == ["Brice ONDO"]
    assert "page_text" not in payload
    assert "Texte interne protege." not in payload.values()
    assert "storage_key" not in payload
    assert "url" not in payload
    assert "session_key" not in payload
