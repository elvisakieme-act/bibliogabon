from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from search_discovery.services import search_documents


def _error(code: str, status: int) -> JsonResponse:
    return JsonResponse({"error": code}, status=status)


def _parse_positive_int(value: str, error_code: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc
    if parsed < 1:
        raise ValueError(error_code)
    return parsed


@require_GET
def search_documents_view(request) -> JsonResponse:
    try:
        publication_year = None
        if "year" in request.GET:
            publication_year = _parse_positive_int(request.GET.get("year"), "invalid_year")
        limit = _parse_positive_int(request.GET.get("limit", "20"), "invalid_limit")
    except ValueError as exc:
        return _error(str(exc), 400)

    results = search_documents(
        query=request.GET.get("q", ""),
        domain_slug=request.GET.get("domain", ""),
        language_code=request.GET.get("language", ""),
        access_model=request.GET.get("access", ""),
        publication_year=publication_year,
        limit=limit,
    )
    return JsonResponse({"count": len(results), "results": results}, status=200)
