"""Les types publics doivent décrire les réponses publiques réelles.

Le garde-fou existait déjà — pour `/gestion` seulement
(`api/staff/v1/tests/test_frontend_type_parity.py`). Côté public, rien. Le
défaut qu'il aurait attrapé s'est produit : `SearchResult` ne déclarait pas
`document_type`, que la recherche renvoie pourtant depuis toujours. Sans
conséquence visible, puisqu'un champ ignoré ne casse rien — mais c'est
exactement ainsi qu'un champ *manquant* passe aussi, et celui-là casse.

Même méthode que pour la version back-office, et pour les mêmes raisons :

- l'égalité est **exacte**, pas l'inclusion. Un champ en trop côté client est
  un `undefined` lu comme une valeur absente ; un champ en trop côté serveur
  est soit une information ignorée, soit quelque chose qui n'aurait pas dû
  sortir ;
- le fichier du dépôt est lu sans exécuter TypeScript ;
- un chemin introuvable **échoue** au lieu de sauter, sinon une réorganisation
  du frontend ferait disparaître le garde-fou en silence.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from api.staff.v1.tests.test_frontend_type_parity import declared_fields
from catalog.models import AcademicDomain, Author, Document, DocumentAuthor, DocumentType
from document_ingestion.pipeline import ingest_document_file
from search_discovery.services import rebuild_document_search_index

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "document_ingestion"
    / "tests"
    / "fixtures"
    / "sample-3-pages.pdf"
)


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def reader(db):
    return User.objects.create_user(
        email="parite-publique@bibliogabon.ga",
        password="passphrase",
        account_type=User.AccountType.INDIVIDUAL,
    )


@pytest.fixture
def api(reader):
    client = APIClient()
    client.force_authenticate(user=reader)
    return client


@pytest.fixture
def published_document(db, local_storage, reader):
    """Un document complet : domaine, type, auteur, fichier ingéré, indexé.

    Un document dépouillé donnerait une charge dépouillée, et la parité
    passerait sur une réponse que l'écran ne verra jamais.
    """
    domain = AcademicDomain.objects.create(name="Droit public", slug="droit-public")
    document_type = DocumentType.objects.create(name="Cours", slug="cours")
    document = Document.objects.create(
        title="Document de parité publique",
        slug="parite-publique",
        abstract="Un résumé, parce qu'un champ vide ne prouve rien.",
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_status=Document.PublicationStatus.PUBLISHED,
        published_at=timezone.now(),
        language_code="fr",
        publication_year=2026,
    )
    author = Author.objects.create(display_name="Autrice de parité")
    DocumentAuthor.objects.create(document=document, author=author, position=1)
    with FIXTURE.open("rb") as handle:
        ingest_document_file(document=document, fileobj=handle, original_filename="s.pdf")
    rebuild_document_search_index(document)
    return document


def assert_parity(interface: str, payload: dict) -> None:
    served = set(payload)
    declared = declared_fields(interface)
    assert served == declared, (
        f"{interface} : le serveur renvoie {sorted(served - declared)} en plus, "
        f"et le type déclare {sorted(declared - served)} que le serveur ne "
        f"renvoie pas."
    )


@pytest.mark.django_db
def test_document_metadata_matches_the_catalogue_payload(api, published_document):
    payload = api.get(
        reverse("api-v1:catalog-document-detail", kwargs={"document_id": published_document.pk})
    ).json()
    assert_parity("DocumentMetadata", payload)


@pytest.mark.django_db
def test_document_metadata_matches_the_list_payload_too(api, published_document):
    """La liste et le détail doivent renvoyer la même forme.

    Le frontend les lit avec le même type. Si le détail portait un champ de
    plus, l'écran de liste lirait `undefined` sans qu'aucun test ne bronche.
    """
    results = api.get(reverse("api-v1:catalog-documents")).json()["results"]
    assert results, "le document publié devrait figurer au catalogue"
    assert_parity("DocumentMetadata", results[0])


@pytest.mark.django_db
def test_search_result_matches_the_search_payload(api, published_document):
    results = api.get(reverse("api-v1:search"), {"q": "parité"}).json()["results"]
    assert results, "le document indexé devrait remonter"
    assert_parity("SearchResult", results[0])


@pytest.mark.django_db
def test_domain_summary_matches_the_domains_payload(api, published_document):
    results = api.get(reverse("api-v1:catalog-domains")).json()["results"]
    assert results
    assert_parity("DomainSummary", results[0])


@pytest.mark.django_db
def test_document_type_summary_matches_the_types_payload(api, published_document):
    results = api.get(reverse("api-v1:catalog-types")).json()["results"]
    assert results
    assert_parity("DocumentTypeSummary", results[0])


@pytest.mark.django_db
def test_reader_session_and_page_match_the_reader_payloads(api, published_document):
    # Le document est en accès libre : aucun droit à accorder, donc la parité
    # est mesurée sur le parcours le plus simple, pas sur un montage.
    session = api.post(
        reverse("api-v1:reader-session-create"),
        {"document_id": published_document.pk},
        format="json",
    ).json()
    assert_parity("ReaderSession", session)

    page = api.get(
        reverse(
            "api-v1:reader-page",
            kwargs={"session_key": session["session_key"], "page_number": 1},
        )
    ).json()
    assert_parity("ReaderPage", page)


@pytest.mark.django_db
def test_favorite_item_matches_the_favorites_payload(api, published_document):
    api.post(
        reverse("api-v1:favorite-list-create"),
        {"document_id": published_document.pk},
        format="json",
    )
    results = api.get(reverse("api-v1:favorite-list-create")).json()["results"]
    assert results
    assert_parity("FavoriteItem", results[0])


@pytest.mark.django_db
def test_api_user_matches_the_profile_payload(api, reader):
    assert_parity("ApiUser", api.get(reverse("api-v1:me")).json())
