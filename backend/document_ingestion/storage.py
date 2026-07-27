from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings


PUBLIC_REFERENCE_PREFIXES = ("http://", "https://", "file://")


def storage_key_is_public_reference(value: str) -> bool:
    return value.lower().startswith(PUBLIC_REFERENCE_PREFIXES)


def slugify_filename(filename: str) -> str:
    path_name = Path(filename).name
    stem = Path(path_name).stem.lower()
    suffix = Path(path_name).suffix.lower()
    safe_stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return f"{safe_stem or 'document'}{suffix}"


def build_private_storage_key(
    *,
    document,
    version_label: str,
    original_filename: str,
    checksum_sha256: str,
) -> str:
    checksum_prefix = checksum_sha256[:8]
    filename = slugify_filename(original_filename)
    prefix = settings.DOCUMENT_STORAGE_KEY_PREFIX.strip("/")
    return f"{prefix}/{document.pk}/versions/{version_label}/{checksum_prefix}/{filename}"
