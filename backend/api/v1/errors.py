from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def error_response(
    code: str,
    message: str,
    status_code: int,
    field_errors: dict | None = None,
) -> Response:
    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "field_errors": field_errors or {},
            }
        },
        status=status_code,
    )


def _field_errors(data) -> dict:
    if not isinstance(data, dict):
        return {}
    if "detail" in data:
        return {}
    return {key: value for key, value in data.items()}


def _message(data) -> str:
    if isinstance(data, dict) and "detail" in data:
        return str(data["detail"])
    return "The request is invalid."


def _code(exc, response) -> str:
    default_code = getattr(exc, "default_code", "")
    if default_code:
        return str(default_code)
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        return "authentication_required"
    if response.status_code == status.HTTP_403_FORBIDDEN:
        return "permission_denied"
    if response.status_code == status.HTTP_404_NOT_FOUND:
        return "not_found"
    return "invalid_request"


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    return error_response(
        code=_code(exc, response),
        message=_message(response.data),
        status_code=response.status_code,
        field_errors=_field_errors(response.data),
    )
