from __future__ import annotations

import io

import boto3
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from moto import mock_aws

from document_ingestion.blob_storage import (
    get_document_storage,
    open_stream,
    save_stream,
)

STORAGE_KEY = "documents/7/versions/v1/2fef47ab/source.pdf"
PAYLOAD = b"%PDF-1.4 " + b"x" * 200_000
BUCKET = "bibliogabon-test-documents"

S3_SETTINGS = {
    "DOCUMENT_STORAGE_BACKEND": "s3",
    "DOCUMENT_STORAGE_BUCKET": BUCKET,
    "DOCUMENT_STORAGE_ENDPOINT_URL": "",
    "DOCUMENT_STORAGE_ACCESS_KEY": "test-access-key",
    "DOCUMENT_STORAGE_SECRET_KEY": "test-secret-key",
    "DOCUMENT_STORAGE_REGION": "us-east-1",
}


class RecordingStream(io.BytesIO):
    """Enregistre la taille de chaque lecture, pour prouver que le fichier
    source est consommé par morceaux et jamais chargé d'un bloc."""

    def __init__(self, data: bytes):
        super().__init__(data)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1, /) -> bytes:
        self.read_sizes.append(size)
        return super().read(size)


@pytest.fixture
def filesystem_storage(tmp_path, settings):
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ROOT = str(tmp_path)
    return tmp_path


def test_filesystem_backend_round_trips_at_the_exact_key(filesystem_storage):
    save_stream(STORAGE_KEY, io.BytesIO(PAYLOAD))

    assert (filesystem_storage / STORAGE_KEY).is_file()
    with open_stream(STORAGE_KEY) as handle:
        assert handle.read() == PAYLOAD


def test_filesystem_backend_overwrites_without_renaming_the_key(filesystem_storage):
    save_stream(STORAGE_KEY, io.BytesIO(PAYLOAD))
    save_stream(STORAGE_KEY, io.BytesIO(b"remplacement"))

    stored = sorted(p.name for p in (filesystem_storage / STORAGE_KEY).parent.iterdir())
    assert stored == ["source.pdf"], "Django renomme en cas de collision"
    with open_stream(STORAGE_KEY) as handle:
        assert handle.read() == b"remplacement"


def test_save_stream_consumes_the_source_in_chunks(filesystem_storage):
    stream = RecordingStream(PAYLOAD)

    save_stream(STORAGE_KEY, stream)

    assert stream.read_sizes, "la source n'a jamais été lue"
    assert -1 not in stream.read_sizes, "le fichier entier a été chargé en mémoire"
    assert len(stream.read_sizes) >= 2, "la source a été lue en une seule fois"


@mock_aws
def test_s3_backend_round_trips_at_the_exact_key(settings):
    for name, value in S3_SETTINGS.items():
        setattr(settings, name, value)
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)

    save_stream(STORAGE_KEY, io.BytesIO(PAYLOAD))

    stored = boto3.client("s3", region_name="us-east-1").get_object(
        Bucket=BUCKET, Key=STORAGE_KEY
    )
    assert stored["Body"].read() == PAYLOAD
    with open_stream(STORAGE_KEY) as handle:
        assert handle.read() == PAYLOAD


@mock_aws
def test_s3_object_is_not_publicly_readable(settings):
    for name, value in S3_SETTINGS.items():
        setattr(settings, name, value)
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket=BUCKET)

    save_stream(STORAGE_KEY, io.BytesIO(PAYLOAD))

    grants = client.get_object_acl(Bucket=BUCKET, Key=STORAGE_KEY)["Grants"]
    public = [
        grant
        for grant in grants
        if "AllUsers" in (grant.get("Grantee", {}).get("URI") or "")
        or "AuthenticatedUsers" in (grant.get("Grantee", {}).get("URI") or "")
    ]
    assert public == [], "l'objet source est lisible publiquement"


@mock_aws
def test_s3_backend_overwrites_without_renaming_the_key(settings):
    for name, value in S3_SETTINGS.items():
        setattr(settings, name, value)
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket=BUCKET)

    save_stream(STORAGE_KEY, io.BytesIO(PAYLOAD))
    save_stream(STORAGE_KEY, io.BytesIO(b"remplacement"))

    keys = [item["Key"] for item in client.list_objects_v2(Bucket=BUCKET)["Contents"]]
    assert keys == [STORAGE_KEY]
    assert client.get_object(Bucket=BUCKET, Key=STORAGE_KEY)["Body"].read() == b"remplacement"


def test_unknown_backend_is_rejected(settings):
    settings.DOCUMENT_STORAGE_BACKEND = "dropbox"

    with pytest.raises(ImproperlyConfigured):
        get_document_storage()


@override_settings(DOCUMENT_STORAGE_BACKEND="s3", DOCUMENT_STORAGE_BUCKET="")
def test_s3_backend_requires_a_bucket():
    with pytest.raises(ImproperlyConfigured):
        get_document_storage()
