"""Suppression d'une arborescence d'objets stockés.

Le tuilage IIIF produit des dizaines d'objets par page, sans ligne en base :
leurs clés sont déterministes, donc le préfixe suffit à les retrouver. Mais
une réingestion doit alors les effacer par préfixe, faute de quoi elle
laisserait derrière elle les tuiles de la version précédente — des objets que
plus rien ne référence et qu'aucun inventaire ne retrouverait.
"""

from __future__ import annotations

import io

import pytest

from document_ingestion.blob_storage import delete_prefix, get_document_storage, save_stream


@pytest.fixture
def local_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    return tmp_path


def put(key: str) -> None:
    save_stream(key, io.BytesIO(b"contenu"))


@pytest.mark.django_db
def test_it_removes_every_object_under_the_prefix(local_storage):
    for key in (
        "documents/1/versions/v1/pages/0001/tiles/info.json",
        "documents/1/versions/v1/pages/0001/tiles/0,0,512,512/512,/0/default.webp",
        "documents/1/versions/v1/pages/0002/tiles/full/max/0/default.webp",
    ):
        put(key)

    removed = delete_prefix("documents/1/versions/v1/pages")

    assert removed == 3
    storage = get_document_storage()
    assert not storage.exists("documents/1/versions/v1/pages/0001/tiles/info.json")


@pytest.mark.django_db
def test_it_removes_nothing_outside_the_prefix(local_storage):
    """La direction qui compte : un préfixe trop large effacerait les objets
    d'un autre document, et rien ne le signalerait avant qu'un lecteur ouvre
    une page vide."""
    put("documents/1/versions/v1/pages/0001/tiles/info.json")
    put("documents/2/versions/v1/pages/0001/tiles/info.json")
    put("documents/1/versions/v1/source.pdf")

    delete_prefix("documents/1/versions/v1/pages")

    storage = get_document_storage()
    assert storage.exists("documents/2/versions/v1/pages/0001/tiles/info.json")
    assert storage.exists("documents/1/versions/v1/source.pdf")


@pytest.mark.django_db
def test_an_absent_prefix_is_not_an_error(local_storage):
    """Une version jamais tuilée, ou déjà nettoyée : la réingestion ne doit
    pas échouer pour autant."""
    assert delete_prefix("documents/9999/versions/v1/pages") == 0
