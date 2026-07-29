from rest_framework.test import APIClient

from api.v1.errors import error_response


def test_api_v1_index_returns_version_payload():
    client = APIClient()

    response = client.get("/api/v1/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "BiblioGABON API",
        "version": "v1",
        "docs": "/api/docs/",
        "schema": "/api/v1/schema/",
    }


def test_openapi_schema_route_exists():
    client = APIClient()

    response = client.get("/api/v1/schema/")

    assert response.status_code == 200
    assert "openapi" in response.content.decode("utf-8").lower()


def test_swagger_docs_route_exists():
    client = APIClient()

    response = client.get("/api/docs/")

    assert response.status_code == 200


def test_error_response_uses_standard_envelope():
    response = error_response(
        code="invalid_request",
        message="The request is invalid.",
        status_code=400,
        field_errors={"email": ["This field is required."]},
    )

    assert response.status_code == 400
    assert response.data == {
        "error": {
            "code": "invalid_request",
            "message": "The request is invalid.",
            "field_errors": {"email": ["This field is required."]},
        }
    }
