import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_openapi_schema_lists_public_v1_endpoints():
    client = APIClient()

    response = client.get("/api/v1/schema/?format=json")

    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    required_paths = [
        "/api/v1/",
        "/api/v1/auth/register/",
        "/api/v1/auth/token/",
        "/api/v1/auth/token/refresh/",
        "/api/v1/auth/logout/",
        "/api/v1/me/",
        "/api/v1/catalog/documents/",
        "/api/v1/catalog/documents/{document_id}/",
        "/api/v1/catalog/domains/",
        "/api/v1/catalog/authors/",
        "/api/v1/search/",
        "/api/v1/reader/sessions/",
        "/api/v1/reader/sessions/{session_key}/pages/{page_number}/",
        "/api/v1/reader/sessions/{session_key}/",
        "/api/v1/me/favorites/",
        "/api/v1/me/favorites/{document_id}/",
        "/api/v1/me/reading-progress/",
        "/api/v1/me/reading-progress/{document_id}/",
    ]
    for path in required_paths:
        assert path in paths

    assert (
        paths["/api/v1/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ApiIndex"
    )
    assert paths["/api/v1/catalog/documents/"]["get"]["operationId"] == "v1_catalog_documents_list"
    assert (
        paths["/api/v1/catalog/documents/{document_id}/"]["get"]["operationId"]
        == "v1_catalog_documents_retrieve"
    )


@pytest.mark.django_db
def test_openapi_schema_defines_bearer_auth():
    client = APIClient()

    response = client.get("/api/v1/schema/?format=json")

    assert response.status_code == 200
    components = response.json()["components"]
    security_schemes = components["securitySchemes"]
    assert "jwtAuth" in security_schemes
    assert security_schemes["jwtAuth"]["type"] == "http"
    assert security_schemes["jwtAuth"]["scheme"] == "bearer"
