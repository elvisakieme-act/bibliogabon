"""Les types TypeScript doivent décrire les réponses réelles.

Les écrans sont couverts par des tests à stubs. Leur faiblesse est connue : si
le stub mentait, tout passerait au vert et l'écran se casserait en production.
Ce test confronte donc les interfaces déclarées dans
`frontend/src/api/types.ts` aux réponses que le serveur produit vraiment.

Un champ **en trop côté client** est un `undefined` qu'un écran lira comme une
valeur absente. Un champ **en trop côté serveur** est soit une information que
l'écran ignore, soit — plus grave — quelque chose qui n'aurait pas dû sortir.
Les deux sens comptent, donc l'égalité est exacte et non l'inclusion.

Comme pour la parité des énumérations, ce test lit le fichier du dépôt sans
exécuter TypeScript, et un chemin introuvable échoue au lieu de sauter.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from django.urls import reverse
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
from document_ingestion.pipeline import ingest_document_file

TYPES_FILE = Path(__file__).resolve().parents[5] / "frontend" / "src" / "api" / "types.ts"
FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "document_ingestion"
    / "tests"
    / "fixtures"
    / "sample-3-pages.pdf"
)


def declared_fields(interface: str) -> set[str]:
    """Champs d'une interface TypeScript, par lecture du fichier."""
    assert TYPES_FILE.is_file(), (
        f"{TYPES_FILE} est introuvable. Si le frontend a bouge, corrigez ce "
        f"chemin : sauter le test ferait disparaitre le garde-fou en silence."
    )
    source = TYPES_FILE.read_text(encoding="utf-8")
    match = re.search(rf"export interface {interface} \{{(.*?)\n\}}", source, re.S)
    assert match, f"interface {interface} absente de types.ts"
    return {found.group(1) for found in re.finditer(r"^\s{2}(\w+)\??:", match.group(1), re.M)}


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    return tmp_path


@pytest.fixture
def moderator(db):
    return User.objects.create_user(
        email="parite@bibliogabon.ga",
        password="passphrase",
        account_type=User.AccountType.CONTENT_ADMIN,
    )


@pytest.fixture
def api(moderator):
    client = APIClient()
    client.force_authenticate(user=moderator)
    return client


@pytest.fixture
def full_document(local_storage, db):
    """Un document où **aucun** champ optionnel n'est nul : un document creux
    laisserait les objets imbriqués hors comparaison."""
    domain = AcademicDomain.objects.create(name="Droit", slug="droit-parite")
    document_type = DocumentType.objects.create(name="Cours", slug="cours-parite")
    document = Document.objects.create(
        title="Document complet",
        slug="document-complet-parite",
        abstract="Resume",
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=Document.AccessModel.FREE,
        publication_year=2026,
    )
    author = Author.objects.create(display_name="Aline NZE", affiliation="UOB")
    DocumentAuthor.objects.create(
        document=document, author=author, role=DocumentAuthor.Role.AUTHOR, position=1
    )
    RightsAgreement.objects.create(
        document=document,
        rights_holder_name="Aline NZE",
        agreement_type=RightsAgreement.AgreementType.OPEN_LICENSE,
        access_model=Document.AccessModel.FREE,
        withdrawal_rule=RightsAgreement.WithdrawalRule.AUTHOR_REQUEST,
    )
    with FIXTURE.open("rb") as handle:
        ingest_document_file(document=document, fileobj=handle, original_filename="s.pdf")
    return document


def test_staff_document_matches_its_declared_type(api, full_document):
    payload = api.get(
        reverse("api-staff-v1:document-detail", kwargs={"document_id": full_document.pk})
    ).json()

    assert set(payload) == declared_fields("StaffDocument")


def test_the_nested_objects_match_their_declared_types(api, full_document):
    payload = api.get(
        reverse("api-staff-v1:document-detail", kwargs={"document_id": full_document.pk})
    ).json()

    assert set(payload["academic_domain"]) == declared_fields("StaffNamedRef")
    assert set(payload["authors"][0]) == declared_fields("StaffAuthor")
    assert set(payload["rights"]) == declared_fields("StaffRights")
    assert set(payload["ingestion"]) == declared_fields("StaffIngestionSummary")


def test_the_ingestion_status_matches_its_declared_type(api, full_document):
    payload = api.get(
        reverse("api-staff-v1:document-ingestion", kwargs={"document_id": full_document.pk})
    ).json()

    assert set(payload) == declared_fields("StaffIngestionStatus")
    assert set(payload["version"]) == {
        "version_label",
        "status",
        "is_current",
        "page_count",
        "processed_at",
    }
    assert set(payload["job"]) == {
        "status",
        "retry_count",
        "error_code",
        "error_message",
        "started_at",
        "completed_at",
    }


def test_the_author_registry_row_matches_its_declared_type(api, full_document):
    payload = api.get(reverse("api-staff-v1:author-list")).json()

    assert set(payload["results"][0]) == declared_fields("StaffAuthorProfile")


def test_the_index_matches_its_declared_type(api):
    payload = api.get(reverse("api-staff-v1:index")).json()

    assert set(payload) == declared_fields("StaffIndex")


def test_the_error_envelope_matches_its_declared_type(api):
    """L'enveloppe d'erreur est le contrat le plus utilisé du produit : chaque
    formulaire en dépend pour placer ses messages."""
    payload = api.get(
        reverse("api-staff-v1:document-detail", kwargs={"document_id": 999999})
    ).json()

    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"code", "message", "field_errors"}


def test_a_paginated_page_matches_its_declared_type(api, full_document):
    payload = api.get(reverse("api-staff-v1:document-list")).json()

    assert set(payload) == {"count", "next", "previous", "results"}


def test_no_staff_payload_names_a_stored_object(api, full_document):
    """Redit ici ce que les tests d'écran vérifient côté rendu : la règle vaut
    d'abord sur la charge utile, avant tout gabarit."""
    paths = [
        reverse("api-staff-v1:document-list"),
        reverse("api-staff-v1:document-detail", kwargs={"document_id": full_document.pk}),
        reverse("api-staff-v1:document-ingestion", kwargs={"document_id": full_document.pk}),
        reverse("api-staff-v1:author-list"),
    ]
    for path in paths:
        body = api.get(path).content.decode()
        assert not re.search(r"\.pdf|://|storage|bucket", body, re.I), path


def test_the_upload_endpoint_still_refuses_an_unaccepted_type(api, full_document, settings):
    settings.DOCUMENT_UPLOAD_ACCEPTED_MIME_TYPES = ["application/pdf"]

    response = api.post(
        reverse("api-staff-v1:document-source", kwargs={"document_id": full_document.pk}),
        data={"file": io.BytesIO(b"\x89PNG\r\n")},
        format="multipart",
    )

    assert response.status_code == 415
