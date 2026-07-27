from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings


def storage_key_is_public_reference(value: str) -> bool:
    normalized = value.strip()
    lowered = normalized.lower()
    parsed = urlparse(normalized)
    if parsed.scheme or parsed.netloc:
        return True
    if lowered.startswith("//"):
        return True
    return ".." in normalized.split("/")


def normalize_key_segment(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "default"


def slugify_filename(filename: str) -> str:
    path_name = Path(filename).name
    stem = Path(path_name).stem.lower()
    suffix = Path(path_name).suffix.lower()
    safe_stem = normalize_key_segment(stem)
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
    safe_version_label = normalize_key_segment(version_label)
    return f"{prefix}/{document.pk}/versions/{safe_version_label}/{checksum_prefix}/{filename}"
