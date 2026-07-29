from __future__ import annotations

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


def database_is_healthy() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return False
    return True


@never_cache
@require_GET
def health(request):
    database_status = "ok" if database_is_healthy() else "unavailable"
    status_code = 200 if database_status == "ok" else 503
    payload = {
        "status": "ok" if status_code == 200 else "unavailable",
        "checks": {
            "application": "ok",
            "database": database_status,
        },
    }
    return JsonResponse(payload, status=status_code)
