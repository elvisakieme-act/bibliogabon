import pytest
from rest_framework.test import APIClient


EXPECTED_RESPONSE_CODES = {
    ("/api/v1/", "get"): {"200", "401"},
    ("/api/v1/auth/register/", "post"): {"201", "400", "409", "415"},
    ("/api/v1/auth/token/", "post"): {"200", "400", "401", "415"},
    ("/api/v1/auth/token/refresh/", "post"): {"200", "400", "401", "415"},
    ("/api/v1/auth/logout/", "post"): {"204", "400", "401", "403", "415"},
    ("/api/v1/me/", "get"): {"200", "401"},
    ("/api/v1/me/", "patch"): {"200", "400", "401", "415"},
    ("/api/v1/catalog/documents/", "get"): {"200", "401", "404"},
    ("/api/v1/catalog/documents/{document_id}/", "get"): {"200", "401", "404"},
    ("/api/v1/catalog/domains/", "get"): {"200", "401", "404"},
    ("/api/v1/catalog/authors/", "get"): {"200", "401", "404"},
    ("/api/v1/search/", "get"): {"200", "400", "401", "404"},
    ("/api/v1/reader/sessions/", "post"): {
        "201",
        "400",
        "401",
        "403",
        "404",
        "415",
    },
    ("/api/v1/reader/sessions/{session_key}/pages/{page_number}/", "get"): {
        "200",
        "401",
        "403",
        "404",
    },
    ("/api/v1/reader/sessions/{session_key}/", "delete"): {"204", "401", "403"},
    ("/api/v1/me/favorites/", "get"): {"200", "401", "404"},
    ("/api/v1/me/favorites/", "post"): {"200", "201", "401", "404", "415"},
    ("/api/v1/me/favorites/{document_id}/", "delete"): {"204", "401"},
    ("/api/v1/me/reading-progress/", "get"): {"200", "401", "404"},
    ("/api/v1/me/reading-progress/{document_id}/", "patch"): {
        "200",
        "400",
        "401",
        "403",
        "404",
        "415",
    },
}

REQUIRED_AUTH_OPERATIONS = {
    ("/api/v1/auth/logout/", "post"),
    ("/api/v1/me/", "get"),
    ("/api/v1/me/", "patch"),
    ("/api/v1/me/favorites/", "get"),
    ("/api/v1/me/favorites/", "post"),
    ("/api/v1/me/favorites/{document_id}/", "delete"),
    ("/api/v1/me/reading-progress/", "get"),
    ("/api/v1/me/reading-progress/{document_id}/", "patch"),
}


def get_schema():
    response = APIClient().get("/api/v1/schema/?format=json")
    assert response.status_code == 200
    return response.json()


@pytest.mark.django_db
def test_openapi_schema_lists_public_v1_endpoints():
    schema = get_schema()
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
    components = get_schema()["components"]
    security_schemes = components["securitySchemes"]
    assert "jwtAuth" in security_schemes
    assert security_schemes["jwtAuth"]["type"] == "http"
    assert security_schemes["jwtAuth"]["scheme"] == "bearer"


@pytest.mark.django_db
def test_openapi_operations_document_auth_media_types_examples_and_errors():
    schema = get_schema()

    for (path, method), response_codes in EXPECTED_RESPONSE_CODES.items():
        operation = schema["paths"][path][method]
        assert set(operation["responses"]) == response_codes

        if (path, method) in REQUIRED_AUTH_OPERATIONS:
            assert operation["security"] == [{"jwtAuth": []}]
        else:
            assert {} in operation.get("security", [{}])

        if "requestBody" in operation:
            assert set(operation["requestBody"]["content"]) == {"application/json"}
            request_media = operation["requestBody"]["content"]["application/json"]
            assert "examples" in request_media

        for response_code, response in operation["responses"].items():
            if response_code == "204":
                assert "content" not in response
                continue
            assert set(response["content"]) == {"application/json"}

        success_code = "201" if "201" in operation["responses"] else "200"
        if success_code in operation["responses"]:
            success_media = operation["responses"][success_code]["content"]["application/json"]
            assert "examples" in success_media
