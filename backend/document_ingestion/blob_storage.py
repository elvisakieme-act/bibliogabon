"""Stockage des fichiers sources privés.

Le backend est choisi par `DOCUMENT_STORAGE_BACKEND` :

- `filesystem` : disque local, pour un développeur sans stockage objet ;
- `s3` : n'importe quel fournisseur compatible S3, via `django-storages`.

La clé de stockage (`storage_key`) est le contrat commun aux deux backends :
elle ne change pas quand on bascule, donc les lignes déjà enregistrées
restent valables. Le choix du fournisseur derrière l'endpoint S3 est une
décision de déploiement, pas une décision de code.

Les fichiers sources peuvent peser plusieurs centaines de mégaoctets : ils
transitent toujours par un flux, jamais par un `bytes` complet en mémoire.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files import File
from django.core.files.storage import FileSystemStorage, Storage


def _filesystem_storage() -> FileSystemStorage:
    location = getattr(settings, "DOCUMENT_STORAGE_ROOT", None) or (
        Path(settings.BASE_DIR) / "private-media"
    )
    return FileSystemStorage(location=str(location))


def _s3_storage() -> Storage:
    from storages.backends.s3 import S3Storage

    bucket = getattr(settings, "DOCUMENT_STORAGE_BUCKET", "")
    if not bucket:
        raise ImproperlyConfigured("DOCUMENT_STORAGE_BUCKET is required for the s3 backend")

    return S3Storage(
        bucket_name=bucket,
        endpoint_url=getattr(settings, "DOCUMENT_STORAGE_ENDPOINT_URL", "") or None,
        access_key=getattr(settings, "DOCUMENT_STORAGE_ACCESS_KEY", "") or None,
        secret_key=getattr(settings, "DOCUMENT_STORAGE_SECRET_KEY", "") or None,
        region_name=getattr(settings, "DOCUMENT_STORAGE_REGION", "") or "us-east-1",
        # Aucune ACL publique : la confidentialité repose sur le bucket privé,
        # et rien dans le produit ne doit rendre un objet lisible sans session.
        default_acl=None,
        querystring_auth=True,
        # Garantit la clé exacte : sans cela django-storages suffixe le nom
        # pour éviter une collision, et la storage_key enregistrée ment.
        file_overwrite=True,
    )


_BACKENDS = {
    "filesystem": _filesystem_storage,
    "s3": _s3_storage,
}


def get_document_storage() -> Storage:
    name = getattr(settings, "DOCUMENT_STORAGE_BACKEND", "filesystem")
    try:
        build = _BACKENDS[name]
    except KeyError:
        raise ImproperlyConfigured(
            f"DOCUMENT_STORAGE_BACKEND must be filesystem or s3, got {name!r}"
        ) from None
    return build()


def save_stream(storage_key: str, fileobj: IO[bytes]) -> None:
    """Écrit un flux à la clé exacte demandée.

    `FileSystemStorage` renommerait le fichier en cas de collision ; on
    supprime donc l'existant au préalable. Le backend S3 gère le cas par
    `file_overwrite`, sans requête supplémentaire.
    """
    storage = get_document_storage()
    if not getattr(storage, "file_overwrite", False) and storage.exists(storage_key):
        storage.delete(storage_key)
    storage.save(storage_key, File(fileobj, name=Path(storage_key).name))


def open_stream(storage_key: str) -> IO[bytes]:
    """Ouvre le contenu privé en lecture. L'appelant referme le flux."""
    return get_document_storage().open(storage_key, "rb")
