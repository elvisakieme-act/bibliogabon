"""Image fidèle d'une page, servie sous session de lecture.

Le lecteur rendait le texte extrait, à plat : un mémoire y perdait ses titres,
ses tableaux, ses figures et ses formules, et les retours à la ligne du PDF
étaient conservés tels quels, si bien qu'un téléphone repliait le texte deux
fois. L'image de la page était pourtant produite à chaque ingestion et jamais
servie — son propre docstring disait déjà qu'elle « n'est servi qu'à travers
une session de lecture autorisée ».

Ce qui distingue cette image de la couverture : la couverture est une vignette
publique d'un document découvrable, l'image de page est **le contenu**. Elle
exige donc une session vivante et un droit de lecture valide, et elle n'est
jamais mise en cache par un intermédiaire partagé.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Entitlement, User
from catalog.models import AcademicDomain, Document, DocumentType
from document_ingestion import tasks
from document_ingestion.pipeline import ingest_document_file
from document_processing.models import DocumentPage
from document_reader.models import PageAccessLog, ReaderSession

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
    settings.DOCUMENT_PAGE_IMAGE_WIDTH = 480
    return tmp_path


def make_document(*, slug: str, access_model: str = Document.AccessModel.FREE) -> Document:
    domain = AcademicDomain.objects.create(name=f"D {slug}", slug=f"d-{slug}")
    document_type = DocumentType.objects.create(name=f"T {slug}", slug=f"t-{slug}")
    return Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        academic_domain=domain,
        document_type=document_type,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
        published_at=timezone.now(),
    )


def ingest_with_images(document: Document):
    with FIXTURE.open("rb") as handle:
        version = ingest_document_file(
            document=document, fileobj=handle, original_filename="s.pdf"
        )
    for page in DocumentPage.objects.filter(version=version):
        tasks.render_page_image.apply(args=[page.pk]).get()
    return version


def image_path(session: ReaderSession, page_number: int = 1) -> str:
    return reverse(
        "api-v1:reader-page-image",
        kwargs={"session_key": str(session.session_key), "page_number": page_number},
    )


@pytest.fixture
def free_session(db, local_storage):
    document = make_document(slug="image-libre")
    version = ingest_with_images(document)
    session = ReaderSession.objects.create(
        document=document,
        version=version,
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )
    return session


# --- Ce qui est servi -------------------------------------------------------


@pytest.mark.django_db
def test_a_live_session_gets_the_rendered_page(client, free_session):
    response = client.get(image_path(free_session))

    assert response.status_code == 200
    assert response["Content-Type"] == "image/webp"
    assert len(b"".join(response.streaming_content)) > 0


@pytest.mark.django_db
def test_serving_the_image_records_the_access(client, free_session):
    """Toute remise de contenu est tracée, quelle que soit la représentation.

    Une image qui ne journaliserait pas offrirait un chemin de lecture non
    tracé : il suffirait d'appeler l'image page après page pour parcourir un
    document sans laisser d'empreinte.
    """
    assert PageAccessLog.objects.count() == 0

    client.get(image_path(free_session, 2))

    log = PageAccessLog.objects.get()
    assert log.page_number == 2
    assert log.session == free_session
    assert log.document == free_session.document


@pytest.mark.django_db
def test_the_image_is_never_cached_by_a_shared_intermediary(client, free_session):
    """Une page lue n'est pas une couverture publique.

    La couverture porte `public, max-age=86400` : elle est destinée à tout le
    monde. Ici, un cache partagé servirait le contenu à qui n'a pas de session.
    """
    response = client.get(image_path(free_session))

    assert "private" in response["Cache-Control"]
    assert "public" not in response["Cache-Control"]


# --- Ce qui ne l'est pas ----------------------------------------------------


@pytest.mark.django_db
def test_an_expired_session_gets_nothing(client, free_session):
    # Le modèle refuse une expiration antérieure au début : on recule les deux,
    # ce qui décrit une vraie session ancienne plutôt qu'une ligne impossible.
    ReaderSession.objects.filter(pk=free_session.pk).update(
        started_at=timezone.now() - timezone.timedelta(hours=2),
        expires_at=timezone.now() - timezone.timedelta(hours=1),
    )

    response = client.get(image_path(free_session))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "session_inactive"


@pytest.mark.django_db
def test_an_unknown_session_gets_nothing(client, local_storage):
    response = client.get(
        reverse(
            "api-v1:reader-page-image",
            kwargs={
                "session_key": "550e8400-e29b-41d4-a716-446655440000",
                "page_number": 1,
            },
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_page_beyond_the_document_gets_nothing(client, free_session):
    response = client.get(image_path(free_session, 99))

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_restricted_document_requires_an_entitlement(client, local_storage):
    """Le droit de lecture vaut pour l'image comme pour le texte.

    C'est le point où une seconde écriture de la règle d'autorisation ferait
    le plus de dégâts : l'image livre le contenu, pas un résumé.
    """
    reader = User.objects.create_user(
        email="image-sans-droit@bibliogabon.ga",
        password="passphrase",
        account_type=User.AccountType.INDIVIDUAL,
    )
    document = make_document(
        slug="image-restreinte", access_model=Document.AccessModel.SUBSCRIPTION
    )
    version = ingest_with_images(document)
    session = ReaderSession.objects.create(
        document=document,
        version=version,
        user=reader,
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=reader)

    refused = client.get(image_path(session))
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "entitlement_required"

    Entitlement.objects.create(
        user=reader,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=str(document.pk),
        source=Entitlement.Source.ADMIN_GRANT,
        starts_at=timezone.now() - timezone.timedelta(minutes=1),
    )

    assert client.get(image_path(session)).status_code == 200


@pytest.mark.django_db
def test_a_session_of_another_user_is_refused(client, local_storage):
    owner = User.objects.create_user(
        email="image-proprietaire@bibliogabon.ga",
        password="passphrase",
        account_type=User.AccountType.INDIVIDUAL,
    )
    intruder = User.objects.create_user(
        email="image-intrus@bibliogabon.ga",
        password="passphrase",
        account_type=User.AccountType.INDIVIDUAL,
    )
    document = make_document(slug="image-autrui")
    version = ingest_with_images(document)
    session = ReaderSession.objects.create(
        document=document,
        version=version,
        user=owner,
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=intruder)

    response = client.get(image_path(session))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "access_denied"


@pytest.mark.django_db
def test_a_page_without_a_rendered_image_falls_back_rather_than_failing(client, local_storage):
    """Une page traitée dont le rendu manque : 404, jamais une erreur serveur.

    Le lecteur doit pouvoir retomber sur le texte, ce qu'une 500 lui
    interdirait.
    """
    from document_ingestion.models import DocumentAsset

    document = make_document(slug="image-absente")
    version = ingest_with_images(document)
    # L'ingestion rend les images : décrire une page sans rendu demande de
    # retirer l'objet, pas de s'abstenir de le produire.
    DocumentAsset.objects.filter(
        page__version=version, asset_type=DocumentAsset.AssetType.PAGE_IMAGE
    ).delete()
    session = ReaderSession.objects.create(
        document=document,
        version=version,
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )

    response = client.get(image_path(session))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- L'invariant de confidentialité ----------------------------------------


@pytest.mark.django_db
def test_the_response_never_carries_the_real_storage_key(client, free_session):
    """Comparé aux **vraies** valeurs de l'objet, pas à un motif approchant."""
    from document_ingestion.models import DocumentAsset

    asset = DocumentAsset.objects.filter(
        page__version=free_session.version,
        asset_type=DocumentAsset.AssetType.PAGE_IMAGE,
        page__page_number=1,
    ).first()

    response = client.get(image_path(free_session))
    joined = " ".join(f"{k}: {v}" for k, v in response.items())

    assert asset.storage_key not in joined
    assert not re.search(r"storage|bucket|versions/", joined, re.I), joined


# --- L'adresse annoncée dans la charge de la page ---------------------------


@pytest.mark.django_db
def test_the_page_payload_announces_its_image(client, free_session):
    payload = client.get(
        reverse(
            "api-v1:reader-page",
            kwargs={"session_key": str(free_session.session_key), "page_number": 1},
        )
    ).json()

    assert payload["image"] == image_path(free_session, 1)
    assert client.get(payload["image"]).status_code == 200


@pytest.mark.django_db
def test_a_page_without_an_image_announces_none(client, local_storage):
    """Annoncer une adresse pour une page sans rendu ferait demander au lecteur
    une image inexistante à chaque page d'un document dont le rendu a échoué."""
    from document_ingestion.models import DocumentAsset

    document = make_document(slug="annonce-sans-image")
    version = ingest_with_images(document)
    DocumentAsset.objects.filter(
        page__version=version, asset_type=DocumentAsset.AssetType.PAGE_IMAGE
    ).delete()
    session = ReaderSession.objects.create(
        document=document,
        version=version,
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )

    payload = client.get(
        reverse(
            "api-v1:reader-page",
            kwargs={"session_key": str(session.session_key), "page_number": 1},
        )
    ).json()

    assert payload["image"] is None


@pytest.mark.django_db
def test_the_page_payload_carries_the_word_positions(client, free_session):
    """La couche texte a besoin des positions, pas seulement du texte."""
    payload = client.get(
        reverse(
            "api-v1:reader-page",
            kwargs={"session_key": str(free_session.session_key), "page_number": 1},
        )
    ).json()

    assert payload["words"], "la page devrait porter la position de ses mots"
    assert all(len(box) == 5 for box in payload["words"])
    assert all(0 <= value <= 1 for box in payload["words"] for value in box[:4])


@pytest.mark.django_db
def test_the_page_payload_never_names_a_stored_object(client, free_session):
    body = client.get(
        reverse(
            "api-v1:reader-page",
            kwargs={"session_key": str(free_session.session_key), "page_number": 1},
        )
    ).content.decode()

    assert not re.search(r"\.webp|storage|bucket|versions/", body, re.I)
