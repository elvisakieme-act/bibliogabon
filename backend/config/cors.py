from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers


ALLOW_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
ALLOW_HEADERS = "Accept, Authorization, Content-Type"
MAX_AGE_SECONDS = "86400"


class CorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin")
        is_allowed = bool(origin and origin in settings.CORS_ALLOWED_ORIGINS)
        is_preflight = (
            request.method == "OPTIONS"
            and "Access-Control-Request-Method" in request.headers
        )

        if is_allowed and is_preflight:
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if is_allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = ALLOW_METHODS
            response.headers["Access-Control-Allow-Headers"] = ALLOW_HEADERS
            response.headers["Access-Control-Max-Age"] = MAX_AGE_SECONDS
            patch_vary_headers(response, ("Origin",))

        return response
