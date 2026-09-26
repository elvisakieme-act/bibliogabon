"""Stockage des fichiers sources privés.

En développement, on stocke sur le disque local sous un dossier privé, en
utilisant la clé de stockage (`storage_key`) comme chemin relatif. Le jour où
tu passes sur un stockage objet (S3 / MinIO), il suffit de remplacer le backend
`FileSystemStorage` par `S3Boto3Storage` (django-storages) : la même clé de
stockage reste valable, le reste du code ne change pas.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage


def get_document_storage() -> FileSystemStorage:
    location = getattr(settings, "DOCUMENT_STORAGE_ROOT", None) or (
        Path(settings.BASE_DIR) / "private-media"
    )
    return FileSystemStorage(location=str(location))


def save_bytes(storage_key: str, data: bytes) -> None:
    storage = get_document_storage()
    # On garantit la clé exacte : on supprime un éventuel fichier existant
    # (FileSystemStorage renommerait sinon le fichier pour éviter la collision).
    if storage.exists(storage_key):
        storage.delete(storage_key)
    storage.save(storage_key, ContentFile(data))


def read_bytes(storage_key: str) -> bytes:
    storage = get_document_storage()
    with storage.open(storage_key, "rb") as handle:
        return handle.read()