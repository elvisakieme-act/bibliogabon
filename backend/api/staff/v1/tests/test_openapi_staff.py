from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User


@pytest.fixture
def schema(db):
    api = APIClient()
    api.force_authenticate(
        User.objects.create_user(
            email="mod-schema@bibliogabon.ga", password="p",
            account_type=User.AccountType.CONTENT_ADMIN,
        )
    )
    return api.get(reverse("api-staff-v1-schema"), {"format": "json"}).json()


def operations(schema):
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                yield path, method, operation


def test_every_operation_has_a_summary_and_a_description(schema):
    missing = [
        f"{method.upper()} {path}"
        for path, method, operation in operations(schema)
        if not operation.get("summary") or not operation.get("description")
    ]
    assert missing == [], missing


def test_every_operation_declares_its_responses(schema):
    missing = [
        f"{method.upper()} {path}"
        for path, method, operation in operations(schema)
        if not operation.get("responses")
    ]
    assert missing == [], missing


def test_every_operation_has_a_stable_identifier(schema):
    identifiers = [
        operation["operationId"] for _, _, operation in operations(schema)
    ]
    assert all(identifier.startswith("staff_v1_") for identifier in identifiers), identifiers
    assert len(identifiers) == len(set(identifiers)), "identifiants dupliqués"


def test_path_parameters_are_declared(schema):
    undeclared = []
    for path, method, operation in operations(schema):
        if "{" not in path:
            continue
        declared = {
            parameter["name"]
            for parameter in operation.get("parameters", [])
            if parameter.get("in") == "path"
        }
        expected = {
            fragment.split("}")[0] for fragment in path.split("{")[1:]
        }
        if not expected <= declared:
            undeclared.append(f"{method.upper()} {path}: {expected - declared}")
    assert undeclared == [], undeclared


def test_the_upload_endpoint_declares_multipart(schema):
    upload = schema["paths"]["/api/staff/v1/documents/{document_id}/source/"]["post"]

    assert "multipart/form-data" in upload["requestBody"]["content"]


def test_the_staff_schema_still_holds_no_public_path(schema):
    stray = [path for path in schema["paths"] if not path.startswith("/api/staff/v1/")]
    assert stray == [], stray


@pytest.mark.django_db
def test_the_public_schema_still_holds_no_staff_path():
    """Réaffirmé en fin de tranche : sept endpoints staff ont été ajoutés
    depuis le premier contrôle."""
    response = APIClient().get(reverse("api-v1-schema"), {"format": "json"})

    leaked = [path for path in response.json()["paths"] if path.startswith("/api/staff")]
    assert leaked == [], leaked
