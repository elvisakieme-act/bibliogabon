# BiblioGABON Public API V1 Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first public, versioned REST JSON API contract for BiblioGABON under `/api/v1/`.

**Architecture:** Add a dedicated `api` Django app that owns HTTP serialization, JWT authentication, pagination, normalized errors, and OpenAPI annotations. Existing domain apps remain the source of truth for business rules; API views call catalog, search, reader, and account services rather than duplicating core authorization logic.

**Tech Stack:** Python 3.12, Django >=5.2,<6.0, Django REST Framework, SimpleJWT, drf-spectacular, pytest, pytest-django.

## Global Constraints

- The API is public, documented, versioned, and JSON-only.
- V1 uses REST under `/api/v1/`.
- Authentication uses JWT, not Django session auth, for API clients.
- Individual user registration is open to the public and creates only `accounts.User.AccountType.INDIVIDUAL`.
- Public catalog and search endpoints can be used anonymously.
- Free or open-access documents can be read anonymously through the secure reader.
- Restricted documents require JWT authentication and an active read entitlement.
- Raw files, storage keys, signed URLs, OCR full text, payment metadata, personal reading history, and private admin data are never exposed through catalog or search payloads.
- Staff workflows, ingestion, publication review, rights administration, reporting, and institutional management remain in Django Admin for this slice.
- Existing legacy `/reader/` and `/search/documents/` endpoints must keep their current behavior. When a task changes a shared service, it must run the legacy tests listed in that task.
- Use TDD: add the failing test, run it red for the expected reason, implement, run green, then commit.
- If dependency installation or import checks fail with the selected package set, stop and report the blocker. Do not silently downgrade Django or replace JWT libraries.

---

## File Structure

```text
backend/
  api/
    __init__.py
    apps.py
    v1/
      __init__.py
      auth.py
      catalog.py
      errors.py
      pagination.py
      reader.py
      serializers.py
      urls.py
      user_library.py
      views.py
      tests/
        __init__.py
        test_api_foundation.py
        test_auth_api.py
        test_catalog_api.py
        test_openapi_schema.py
        test_reader_api_v1.py
        test_user_library_api.py
  config/
    settings.py
    urls.py
  document_reader/
    admin.py
    migrations/
    models.py
    services.py
  pyproject.toml
  pytest.ini
```

Responsibilities:

- `api.v1.errors`: normalized API error payloads and DRF exception handler.
- `api.v1.pagination`: standard page-number pagination.
- `api.v1.auth`: registration, JWT token views, refresh, and logout.
- `api.v1.catalog`: public document, domain, author, and search endpoints.
- `api.v1.reader`: public V1 reader endpoints, including anonymous free reading.
- `api.v1.user_library`: authenticated favorites and resume-oriented reading progress.
- `api.v1.serializers`: request and response serializers shared across V1 endpoints.
- `document_reader.models`: reader sessions, page logs, favorites, and reading progress domain data.
- `document_reader.services`: reader access and personal library operations consumed by API views.

---

### Task 1: API Framework Foundation

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/apps.py`
- Create: `backend/api/v1/__init__.py`
- Create: `backend/api/v1/errors.py`
- Create: `backend/api/v1/pagination.py`
- Create: `backend/api/v1/urls.py`
- Create: `backend/api/v1/views.py`
- Create: `backend/api/v1/tests/__init__.py`
- Create: `backend/api/v1/tests/test_api_foundation.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/config/urls.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/pytest.ini`

**Interfaces:**
- Produces `api.v1.errors.error_response(code: str, message: str, status_code: int, field_errors: dict | None = None) -> rest_framework.response.Response`.
- Produces `api.v1.errors.api_exception_handler(exc, context)`.
- Produces `api.v1.pagination.StandardResultsSetPagination`.
- Produces `GET /api/v1/`.
- Produces `GET /api/v1/schema/`.
- Produces `GET /api/docs/`.

- [ ] **Step 1: Write failing API foundation tests**

Create `backend/api/v1/tests/test_api_foundation.py`:

```python
import pytest
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_api_foundation.py -q
```

Expected: FAIL because `rest_framework`, `api`, or `/api/v1/` is not configured.

- [ ] **Step 3: Add API dependencies**

Modify `backend/pyproject.toml` dependencies:

```toml
dependencies = [
  "Django>=5.2,<6.0",
  "dj-database-url>=2.2,<3.0",
  "psycopg[binary]>=3.2,<4.0",
  "djangorestframework>=3.15,<4.0",
  "djangorestframework-simplejwt>=5.5,<6.0",
  "drf-spectacular[sidecar]>=0.28,<1.0",
]
```

Install the updated project dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run an import smoke check:

```powershell
.\.venv\Scripts\python.exe -c "import django, rest_framework, rest_framework_simplejwt, drf_spectacular; print('api deps ok')"
```

Expected: prints `api deps ok`.

- [ ] **Step 4: Configure Django REST Framework and OpenAPI**

Modify `backend/config/settings.py`.

Add installed apps after Django contrib apps and before project domain apps:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "api",
    "accounts",
    "catalog",
    "document_ingestion",
    "document_processing",
    "document_reader",
    "search_discovery",
    "billing",
    "operations",
    "analytics",
]
```

Add API settings after `LOGGING`:

```python
from datetime import timedelta

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
    "DEFAULT_PAGINATION_CLASS": "api.v1.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "api.v1.errors.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "BiblioGABON API",
    "DESCRIPTION": "Public REST API for BiblioGABON.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
}
```

If `from datetime import timedelta` is added, keep imports grouped at the top of `settings.py`.

- [ ] **Step 5: Implement the API app and foundation helpers**

Create `backend/api/apps.py`:

```python
from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
```

Create `backend/api/v1/errors.py`:

```python
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
```

Create `backend/api/v1/pagination.py`:

```python
from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50
```

Create `backend/api/v1/views.py`:

```python
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def api_index(request):
    return Response(
        {
            "name": "BiblioGABON API",
            "version": "v1",
            "docs": "/api/docs/",
            "schema": "/api/v1/schema/",
        }
    )
```

Create `backend/api/v1/urls.py`:

```python
from django.urls import path

from api.v1.views import api_index

app_name = "api-v1"

urlpatterns = [
    path("", api_index, name="index"),
]
```

Modify `backend/config/urls.py`:

```python
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path("api/v1/schema/", SpectacularAPIView.as_view(api_version="v1"), name="api-v1-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-v1-schema"), name="api-docs"),
    path("api/v1/", include("api.v1.urls")),
    path("admin/", admin.site.urls),
    path("reader/", include("document_reader.urls")),
    path("search/", include("search_discovery.urls")),
]
```

- [ ] **Step 6: Register API tests**

Modify `backend/pytest.ini` and `backend/pyproject.toml` testpaths to include:

```text
api/v1/tests
```

- [ ] **Step 7: Run tests to verify they pass**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_api_foundation.py -q
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
```

Expected: API foundation tests pass, Django checks pass, and SimpleJWT blacklist migrations apply if they are pending.

- [ ] **Step 8: Commit**

```powershell
git add backend/pyproject.toml backend/pytest.ini backend/config/settings.py backend/config/urls.py backend/api
git commit -m "feat: add api v1 foundation"
```

---

### Task 2: JWT Authentication And Current User API

**Files:**
- Create: `backend/api/v1/auth.py`
- Create: `backend/api/v1/serializers.py`
- Create: `backend/api/v1/tests/test_auth_api.py`
- Modify: `backend/api/v1/urls.py`

**Interfaces:**
- Consumes `api.v1.errors.error_response`.
- Produces `RegisterView`.
- Produces `LogoutView`.
- Produces `CurrentUserView`.
- Produces `serialize_user(user) -> dict`.
- Produces endpoints:
  - `POST /api/v1/auth/register/`
  - `POST /api/v1/auth/token/`
  - `POST /api/v1/auth/token/refresh/`
  - `POST /api/v1/auth/logout/`
  - `GET /api/v1/me/`
  - `PATCH /api/v1/me/`

- [ ] **Step 1: Write failing auth tests**

Create `backend/api/v1/tests/test_auth_api.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


def bearer(access_token: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {access_token}"}


@pytest.mark.django_db
def test_register_creates_individual_user_and_returns_tokens():
    client = APIClient()

    response = client.post(
        "/api/v1/auth/register/",
        {
            "email": "reader@example.ga",
            "password": "StrongPass123!",
            "display_name": "Reader One",
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    user = get_user_model().objects.get(email="reader@example.ga")
    assert user.account_type == get_user_model().AccountType.INDIVIDUAL
    assert payload["user"] == {
        "id": user.pk,
        "email": "reader@example.ga",
        "display_name": "Reader One",
        "account_type": "individual",
    }
    assert set(payload["tokens"]) == {"access", "refresh"}
    assert "password" not in str(payload).lower()


@pytest.mark.django_db
def test_register_rejects_duplicate_email_with_409():
    User = get_user_model()
    User.objects.create_user(email="reader@example.ga", password="pass")
    client = APIClient()

    response = client.post(
        "/api/v1/auth/register/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_exists"


@pytest.mark.django_db
def test_token_login_and_me_endpoint_use_jwt_only():
    User = get_user_model()
    user = User.objects.create_user(
        email="reader@example.ga",
        password="StrongPass123!",
        display_name="Reader One",
    )
    client = APIClient()

    token_response = client.post(
        "/api/v1/auth/token/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )

    assert token_response.status_code == 200
    access = token_response.json()["access"]
    me_response = client.get("/api/v1/me/", **bearer(access))
    assert me_response.status_code == 200
    assert me_response.json()["email"] == user.email


@pytest.mark.django_db
def test_me_endpoint_rejects_anonymous_user():
    client = APIClient()

    response = client.get("/api/v1/me/")

    assert response.status_code == 401
    assert response.json()["error"]["code"] in {"authentication_required", "not_authenticated"}


@pytest.mark.django_db
def test_me_patch_updates_only_allowed_profile_fields():
    client = APIClient()
    register = client.post(
        "/api/v1/auth/register/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )
    access = register.json()["tokens"]["access"]

    response = client.patch(
        "/api/v1/me/",
        {"display_name": "Updated Reader", "account_type": "platform_staff"},
        format="json",
        **bearer(access),
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Reader"
    assert response.json()["account_type"] == "individual"


@pytest.mark.django_db
def test_logout_blacklists_refresh_token():
    client = APIClient()
    register = client.post(
        "/api/v1/auth/register/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )
    access = register.json()["tokens"]["access"]
    refresh = register.json()["tokens"]["refresh"]

    response = client.post(
        "/api/v1/auth/logout/",
        {"refresh": refresh},
        format="json",
        **bearer(access),
    )

    assert response.status_code == 204
    refresh_response = client.post(
        "/api/v1/auth/token/refresh/",
        {"refresh": refresh},
        format="json",
    )
    assert refresh_response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_auth_api.py -q
```

Expected: FAIL because auth endpoints are not routed.

- [ ] **Step 3: Implement serializers**

Create or extend `backend/api/v1/serializers.py`:

```python
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers


def serialize_user(user) -> dict:
    return {
        "id": user.pk,
        "email": user.email,
        "display_name": user.display_name,
        "account_type": user.account_type,
    }


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=160)

    def validate_email(self, value):
        email = get_user_model().objects.normalize_email(value)
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "A user with this email already exists.",
                code="email_exists",
            )
        return email


class CurrentUserUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=32)
```

- [ ] **Step 4: Implement auth and me views**

Create `backend/api/v1/auth.py`:

```python
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.v1.errors import error_response
from api.v1.serializers import CurrentUserUpdateSerializer, RegisterSerializer, serialize_user


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            email_errors = serializer.errors.get("email", [])
            if any(getattr(error, "code", "") == "email_exists" for error in email_errors):
                return error_response(
                    code="email_exists",
                    message="A user with this email already exists.",
                    status_code=status.HTTP_409_CONFLICT,
                    field_errors={"email": serializer.errors["email"]},
                )
            return error_response(
                code="invalid_registration",
                message="Registration data is invalid.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors=serializer.errors,
            )
        user = get_user_model().objects.create_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            display_name=serializer.validated_data.get("display_name", ""),
            account_type=get_user_model().AccountType.INDIVIDUAL,
        )
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": serialize_user(user),
                "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)},
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = str(request.data.get("refresh", "")).strip()
        if not refresh_token:
            return error_response(
                code="refresh_token_required",
                message="A refresh token is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors={"refresh": ["This field is required."]},
            )
        try:
            RefreshToken(refresh_token).blacklist()
        except Exception:
            return error_response(
                code="invalid_refresh_token",
                message="The refresh token is invalid.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors={"refresh": ["Invalid refresh token."]},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(serialize_user(request.user), status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = CurrentUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = request.user
        for field in ["display_name", "phone_number"]:
            if field in serializer.validated_data:
                setattr(user, field, serializer.validated_data[field])
        user.save(update_fields=["display_name", "phone_number", "updated_at"])
        return Response(serialize_user(user), status=status.HTTP_200_OK)
```

- [ ] **Step 5: Route auth endpoints**

Modify `backend/api/v1/urls.py`:

```python
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.v1.auth import CurrentUserView, LogoutView, RegisterView
from api.v1.views import api_index

app_name = "api-v1"

urlpatterns = [
    path("", api_index, name="index"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token-obtain"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_auth_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/api/v1/auth.py backend/api/v1/serializers.py backend/api/v1/urls.py backend/api/v1/tests/test_auth_api.py
git commit -m "feat: add jwt auth api"
```

---

### Task 3: Reader API V1 And Anonymous Free Reading

**Files:**
- Create: `backend/api/v1/reader.py`
- Create: `backend/api/v1/tests/test_reader_api_v1.py`
- Modify: `backend/api/v1/urls.py`
- Modify: `backend/document_reader/models.py`
- Modify: `backend/document_reader/services.py`
- Add migration: `backend/document_reader/migrations/`

**Interfaces:**
- Consumes `document_reader.services.start_reader_session`.
- Consumes `document_reader.services.get_reader_page`.
- Produces nullable `ReaderSession.user`.
- Produces nullable `PageAccessLog.user`.
- Produces anonymous free reading through:
  - `POST /api/v1/reader/sessions/`
  - `GET /api/v1/reader/sessions/{session_key}/pages/{page_number}/`
  - `DELETE /api/v1/reader/sessions/{session_key}/`

- [ ] **Step 1: Write failing reader API V1 tests**

Create `backend/api/v1/tests/test_reader_api_v1.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Entitlement
from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_processing.services import attach_extracted_text, create_page_records
from document_reader.models import ReaderSession


def auth_headers(access_token: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {access_token}"}


def create_user_and_token(client, email="reader@example.ga"):
    response = client.post(
        "/api/v1/auth/register/",
        {"email": email, "password": "StrongPass123!"},
        format="json",
    )
    return response.json()["tokens"]["access"], get_user_model().objects.get(email=email)


def create_readable_document(slug="reader-v1-free", access_model=Document.AccessModel.FREE):
    domain = AcademicDomain.objects.create(name=f"Reader {slug}", slug=f"reader-{slug}")
    document = Document.objects.create(
        title=f"Reader {slug}",
        slug=slug,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )
    version = DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=1,
    )
    page = create_page_records(version=version, page_count=1)[0]
    page.status = DocumentPage.Status.PROCESSED
    page.save(update_fields=["status", "updated_at"])
    attach_extracted_text(page=page, text="Texte lisible API V1.", language_code="fr")
    return document


@pytest.mark.django_db
def test_anonymous_user_can_create_free_reader_session():
    client = APIClient()
    document = create_readable_document()

    response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document_id"] == document.pk
    assert ReaderSession.objects.get(session_key=payload["session_key"]).user_id is None


@pytest.mark.django_db
def test_anonymous_user_can_read_page_from_free_session():
    client = APIClient()
    document = create_readable_document()
    session_response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
    )
    session_key = session_response.json()["session_key"]

    response = client.get(f"/api/v1/reader/sessions/{session_key}/pages/1/")

    assert response.status_code == 200
    assert response.json()["text"] == "Texte lisible API V1."
    assert "storage_key" not in response.content.decode("utf-8")


@pytest.mark.django_db
def test_anonymous_user_cannot_create_restricted_reader_session():
    client = APIClient()
    document = create_readable_document(access_model=Document.AccessModel.SUBSCRIPTION)

    response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


@pytest.mark.django_db
def test_authenticated_user_without_entitlement_cannot_create_restricted_session():
    client = APIClient()
    access, _ = create_user_and_token(client)
    document = create_readable_document(
        slug="reader-v1-restricted",
        access_model=Document.AccessModel.SUBSCRIPTION,
    )

    response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
        **auth_headers(access),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "entitlement_required"


@pytest.mark.django_db
def test_authenticated_user_with_entitlement_can_create_restricted_session():
    client = APIClient()
    access, user = create_user_and_token(client)
    document = create_readable_document(
        slug="reader-v1-entitled",
        access_model=Document.AccessModel.SUBSCRIPTION,
    )
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.DOCUMENT,
        scope_id=document.entitlement_scope_id,
        starts_at=timezone.now() - timezone.timedelta(minutes=5),
        ends_at=timezone.now() + timezone.timedelta(minutes=30),
    )

    response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
        **auth_headers(access),
    )

    assert response.status_code == 201
    assert ReaderSession.objects.get(session_key=response.json()["session_key"]).user == user


@pytest.mark.django_db
def test_delete_reader_session_returns_204():
    client = APIClient()
    document = create_readable_document()
    session_response = client.post(
        "/api/v1/reader/sessions/",
        {"document_id": document.pk},
        format="json",
    )

    response = client.delete(
        f"/api/v1/reader/sessions/{session_response.json()['session_key']}/"
    )

    assert response.status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_reader_api_v1.py -q
```

Expected: FAIL because reader V1 endpoints are not routed and reader sessions require a non-null user.

- [ ] **Step 3: Make reader session user nullable**

Modify `backend/document_reader/models.py`:

```python
user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    null=True,
    blank=True,
    on_delete=models.CASCADE,
    related_name="reader_sessions",
)
```

Modify `PageAccessLog.user`:

```python
user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    null=True,
    blank=True,
    on_delete=models.PROTECT,
    related_name="page_access_logs",
)
```

Update `ReaderSession.__str__`:

```python
def __str__(self) -> str:
    reader = self.user if self.user_id else "anonymous"
    return f"{reader} reading {self.document}"
```

Run:

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations document_reader
```

Expected: a migration alters `ReaderSession.user` and `PageAccessLog.user`.

- [ ] **Step 4: Update reader services for anonymous free reading**

Modify `backend/document_reader/services.py`:

```python
def user_can_read_document(user, document: Document, at=None) -> bool:
    if not document_is_reader_accessible(document):
        return False
    if not document_requires_entitlement(document):
        return document.access_model == Document.AccessModel.FREE
    if not _user_is_authenticated(user):
        return False
    return _user_has_document_read_entitlement(user, document, at=at)
```

Keep `start_reader_session` accepting `user=None`:

```python
def start_reader_session(
    *,
    user,
    document: Document,
    client_ip: str = "",
    user_agent: str = "",
    at=None,
) -> ReaderSession:
    at = at or timezone.now()
    if not user_can_read_document(user, document, at=at):
        raise ReaderAccessDenied("User cannot read this document")
    version = get_current_processed_version(document)
    ttl_minutes = int(getattr(settings, "READER_SESSION_TTL_MINUTES", 120))
    with transaction.atomic():
        return ReaderSession.objects.create(
            user=user,
            document=document,
            version=version,
            started_at=at,
            expires_at=at + timezone.timedelta(minutes=ttl_minutes),
            client_ip=client_ip,
            user_agent=user_agent,
            last_seen_at=at,
        )
```

Keep the entitlement re-check inside `_ensure_reader_session_can_read`; the updated `user_can_read_document` returns `False` for anonymous restricted sessions.

- [ ] **Step 5: Implement reader API V1 views**

Create `backend/api/v1/reader.py`:

```python
from __future__ import annotations

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from api.v1.errors import error_response
from catalog.models import Document
from document_reader.exceptions import ReaderAccessDenied, ReaderPageUnavailable, ReaderSessionInactive
from document_reader.models import ReaderSession
from document_reader.services import (
    document_requires_entitlement,
    end_reader_session,
    get_reader_page,
    start_reader_session,
)


def _client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:45]
    return request.META.get("REMOTE_ADDR", "")[:45]


def _user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:300]


class ReaderSessionCreateView(APIView):
    def post(self, request):
        document_id = request.data.get("document_id")
        if not document_id:
            return error_response(
                code="document_required",
                message="document_id is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors={"document_id": ["This field is required."]},
            )
        try:
            document = Document.objects.get(pk=document_id)
        except (TypeError, ValueError, Document.DoesNotExist):
            return error_response(
                code="not_found",
                message="Document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        user = request.user if request.user.is_authenticated else None
        if document_requires_entitlement(document) and user is None:
            return error_response(
                code="authentication_required",
                message="Authentication is required for this document.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            session = start_reader_session(
                user=user,
                document=document,
                client_ip=_client_ip(request),
                user_agent=_user_agent(request),
            )
        except ReaderAccessDenied:
            return error_response(
                code="entitlement_required",
                message="An active read entitlement is required.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {
                "session_key": str(session.session_key),
                "document_id": session.document_id,
                "version_id": session.version_id,
                "expires_at": session.expires_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class ReaderPageView(APIView):
    def get(self, request, session_key, page_number: int):
        try:
            session = ReaderSession.objects.select_related("user", "document", "version").get(
                session_key=session_key
            )
        except ReaderSession.DoesNotExist:
            return error_response("not_found", "Reader session not found.", status.HTTP_404_NOT_FOUND)
        if session.user_id and session.user_id != getattr(request.user, "pk", None):
            return error_response("access_denied", "This session belongs to another user.", status.HTTP_403_FORBIDDEN)
        try:
            return Response(get_reader_page(session=session, page_number=page_number), status=status.HTTP_200_OK)
        except ReaderSessionInactive:
            return error_response("session_inactive", "Reader session is inactive.", status.HTTP_403_FORBIDDEN)
        except ReaderAccessDenied:
            return error_response("entitlement_required", "An active read entitlement is required.", status.HTTP_403_FORBIDDEN)
        except ReaderPageUnavailable:
            return error_response("not_found", "Page not found.", status.HTTP_404_NOT_FOUND)


class ReaderSessionDeleteView(APIView):
    def delete(self, request, session_key):
        try:
            session = ReaderSession.objects.get(session_key=session_key)
        except ReaderSession.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if session.user_id and session.user_id != getattr(request.user, "pk", None):
            return error_response("access_denied", "This session belongs to another user.", status.HTTP_403_FORBIDDEN)
        end_reader_session(session=session)
        return Response(status=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 6: Route reader API V1 endpoints**

Modify `backend/api/v1/urls.py`:

```python
from api.v1.reader import ReaderPageView, ReaderSessionCreateView, ReaderSessionDeleteView

urlpatterns += [
    path("reader/sessions/", ReaderSessionCreateView.as_view(), name="reader-session-create"),
    path(
        "reader/sessions/<uuid:session_key>/pages/<int:page_number>/",
        ReaderPageView.as_view(),
        name="reader-page",
    ),
    path(
        "reader/sessions/<uuid:session_key>/",
        ReaderSessionDeleteView.as_view(),
        name="reader-session-delete",
    ),
]
```

- [ ] **Step 7: Run reader tests**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_reader_api_v1.py document_reader/tests/test_reader_api.py -q
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Expected: new API V1 reader tests pass, legacy reader API tests still pass, and migrations are committed.

- [ ] **Step 8: Commit**

```powershell
git add backend/api/v1/reader.py backend/api/v1/urls.py backend/api/v1/tests/test_reader_api_v1.py backend/document_reader/models.py backend/document_reader/services.py backend/document_reader/migrations
git commit -m "feat: expose secure reader api v1"
```

---

### Task 4: Public Catalog And Search API V1

**Files:**
- Create: `backend/api/v1/catalog.py`
- Create: `backend/api/v1/tests/test_catalog_api.py`
- Modify: `backend/api/v1/serializers.py`
- Modify: `backend/api/v1/urls.py`

**Interfaces:**
- Consumes `document_reader.services.user_can_read_document`.
- Consumes `search_discovery.services.search_documents`.
- Produces `serialize_document_metadata(document, user=None) -> dict`.
- Produces:
  - `GET /api/v1/catalog/documents/`
  - `GET /api/v1/catalog/documents/{id}/`
  - `GET /api/v1/catalog/domains/`
  - `GET /api/v1/catalog/authors/`
  - `GET /api/v1/search/`

- [ ] **Step 1: Write failing catalog/search tests**

Create `backend/api/v1/tests/test_catalog_api.py`:

```python
import pytest
from rest_framework.test import APIClient

from accounts.models import Entitlement
from catalog.models import AcademicDomain, Author, Document, DocumentAuthor
from document_ingestion.models import DocumentVersion
from document_processing.models import DocumentPage
from document_processing.services import attach_extracted_text, create_page_records
from search_discovery.services import rebuild_document_search_index


def create_document(slug, title, access_model=Document.AccessModel.FREE, status=Document.PublicationStatus.PUBLISHED):
    domain, _ = AcademicDomain.objects.get_or_create(slug="droit", defaults={"name": "Droit"})
    document = Document.objects.create(
        title=title,
        slug=slug,
        abstract="Resume public.",
        language_code="fr",
        publication_year=2026,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=status,
    )
    author = Author.objects.create(display_name=f"Auteur {title}", normalized_name=title.lower())
    DocumentAuthor.objects.create(document=document, author=author, position=1)
    version = DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=1,
    )
    page = create_page_records(version=version, page_count=1)[0]
    page.status = DocumentPage.Status.PROCESSED
    page.save(update_fields=["status", "updated_at"])
    attach_extracted_text(page=page, text="Texte interne non expose.", language_code="fr")
    rebuild_document_search_index(document)
    return document


@pytest.mark.django_db
def test_document_list_returns_public_metadata_only():
    client = APIClient()
    document = create_document("droit-public", "Droit public")
    create_document("draft-hidden", "Brouillon", status=Document.PublicationStatus.DRAFT)

    response = client.get("/api/v1/catalog/documents/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    result = payload["results"][0]
    assert result["id"] == document.pk
    assert result["title"] == "Droit public"
    assert result["access"]["can_read"] is True
    assert result["access"]["reason"] == "free"
    assert "Texte interne non expose." not in response.content.decode("utf-8")
    assert "storage_key" not in response.content.decode("utf-8")


@pytest.mark.django_db
def test_restricted_document_detail_public_metadata_requires_auth_for_access():
    client = APIClient()
    document = create_document("restricted", "Document restreint", access_model=Document.AccessModel.SUBSCRIPTION)

    response = client.get(f"/api/v1/catalog/documents/{document.pk}/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == document.pk
    assert payload["access"] == {
        "can_read": False,
        "access_model": "subscription",
        "reason": "authentication_required",
    }


@pytest.mark.django_db
def test_private_document_detail_returns_404():
    client = APIClient()
    document = create_document("private", "Document prive", access_model=Document.AccessModel.PRIVATE)

    response = client.get(f"/api/v1/catalog/documents/{document.pk}/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_domains_and_authors_endpoints_return_public_values():
    client = APIClient()
    create_document("droit-public", "Droit public")

    domains = client.get("/api/v1/catalog/domains/")
    authors = client.get("/api/v1/catalog/authors/")

    assert domains.status_code == 200
    assert domains.json()["results"][0]["slug"] == "droit"
    assert authors.status_code == 200
    assert authors.json()["results"][0]["display_name"] == "Auteur Droit public"


@pytest.mark.django_db
def test_search_endpoint_uses_standard_pagination_and_hides_page_text():
    client = APIClient()
    document = create_document("searchable", "Recherche pedagogique")

    response = client.get("/api/v1/search/?q=interne")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == document.pk
    assert payload["results"][0]["text_match"] is True
    assert "Texte interne non expose." not in response.content.decode("utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_catalog_api.py -q
```

Expected: FAIL because catalog/search API V1 endpoints do not exist.

- [ ] **Step 3: Implement metadata serializers**

Extend `backend/api/v1/serializers.py`:

```python
from document_ingestion.models import DocumentVersion
from document_reader.services import document_requires_entitlement, user_can_read_document


def _ordered_authors(document) -> list[dict]:
    return [
        {
            "id": authorship.author_id,
            "display_name": authorship.author.display_name,
            "role": authorship.role,
        }
        for authorship in document.document_authors.select_related("author").order_by("position")
    ]


def _page_count(document) -> int | None:
    version = (
        DocumentVersion.objects.filter(document=document, is_current=True)
        .order_by("-created_at")
        .first()
    )
    return version.page_count if version else None


def _access_block(document, user=None) -> dict:
    access_model = document.access_model
    if user_can_read_document(user, document):
        reason = "free" if not document_requires_entitlement(document) else "active_entitlement"
        return {"can_read": True, "access_model": access_model, "reason": reason}
    if document_requires_entitlement(document) and not getattr(user, "is_authenticated", False):
        return {"can_read": False, "access_model": access_model, "reason": "authentication_required"}
    if document_requires_entitlement(document):
        return {"can_read": False, "access_model": access_model, "reason": "entitlement_required"}
    return {"can_read": False, "access_model": access_model, "reason": "unavailable"}


def serialize_document_metadata(document, user=None) -> dict:
    domain = None
    if document.academic_domain_id:
        domain = {
            "id": document.academic_domain_id,
            "name": document.academic_domain.name,
            "slug": document.academic_domain.slug,
        }
    owner = document.owner_organization.name if document.owner_organization_id else None
    return {
        "id": document.pk,
        "slug": document.slug,
        "title": document.title,
        "abstract": document.abstract,
        "language_code": document.language_code,
        "publication_year": document.publication_year,
        "document_type": document.category,
        "access_model": document.access_model,
        "domain": domain,
        "authors": _ordered_authors(document),
        "owner": owner,
        "page_count": _page_count(document),
        "cover": None,
        "access": _access_block(document, user=user),
    }
```

- [ ] **Step 4: Implement catalog and search views**

Create `backend/api/v1/catalog.py`:

```python
from __future__ import annotations

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from api.v1.errors import error_response
from api.v1.pagination import StandardResultsSetPagination
from api.v1.serializers import serialize_document_metadata
from catalog.models import AcademicDomain, Author, Document
from search_discovery.services import search_documents


def _published_documents():
    return (
        Document.objects.select_related("academic_domain", "owner_organization")
        .prefetch_related("document_authors__author")
        .filter(publication_status=Document.PublicationStatus.PUBLISHED)
        .exclude(access_model=Document.AccessModel.PRIVATE)
        .order_by("title", "id")
    )


class DocumentListView(APIView):
    def get(self, request):
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(_published_documents(), request, view=self)
        results = [serialize_document_metadata(document, user=request.user) for document in page]
        return paginator.get_paginated_response(results)


class DocumentDetailView(APIView):
    def get(self, request, document_id: int):
        try:
            document = _published_documents().get(pk=document_id)
        except Document.DoesNotExist:
            return error_response(
                code="not_found",
                message="Document not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return Response(serialize_document_metadata(document, user=request.user), status=status.HTTP_200_OK)


class DomainListView(APIView):
    def get(self, request):
        domains = AcademicDomain.objects.filter(is_active=True).order_by("name", "id")
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(domains, request, view=self)
        return paginator.get_paginated_response(
            [{"id": domain.pk, "name": domain.name, "slug": domain.slug} for domain in page]
        )


class AuthorListView(APIView):
    def get(self, request):
        authors = (
            Author.objects.filter(document_authorships__document__in=_published_documents())
            .distinct()
            .order_by("normalized_name", "display_name", "id")
        )
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(authors, request, view=self)
        return paginator.get_paginated_response(
            [{"id": author.pk, "display_name": author.display_name, "author_type": author.author_type} for author in page]
        )


class SearchView(APIView):
    def get(self, request):
        try:
            year = request.query_params.get("year")
            publication_year = int(year) if year else None
        except ValueError:
            return error_response("invalid_year", "year must be an integer.", status.HTTP_400_BAD_REQUEST)
        results = search_documents(
            query=request.query_params.get("q", ""),
            domain_slug=request.query_params.get("domain", ""),
            language_code=request.query_params.get("language", ""),
            access_model=request.query_params.get("access", ""),
            publication_year=publication_year,
            limit=50,
        )
        normalized = []
        for result in results:
            normalized.append(
                {
                    "id": result["document_id"],
                    "title": result["title"],
                    "slug": result["slug"],
                    "abstract": result["abstract"],
                    "language_code": result["language_code"],
                    "publication_year": result["publication_year"],
                    "domain": result["academic_domain"],
                    "authors": result["authors"],
                    "access_model": result["access_model"],
                    "indexed_page_count": result["indexed_page_count"],
                    "score": result["score"],
                    "text_match": result["text_match"],
                }
            )
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(normalized, request, view=self)
        return paginator.get_paginated_response(page)
```

- [ ] **Step 5: Route catalog/search endpoints**

Modify `backend/api/v1/urls.py`:

```python
from api.v1.catalog import AuthorListView, DocumentDetailView, DocumentListView, DomainListView, SearchView

urlpatterns += [
    path("catalog/documents/", DocumentListView.as_view(), name="catalog-documents"),
    path("catalog/documents/<int:document_id>/", DocumentDetailView.as_view(), name="catalog-document-detail"),
    path("catalog/domains/", DomainListView.as_view(), name="catalog-domains"),
    path("catalog/authors/", AuthorListView.as_view(), name="catalog-authors"),
    path("search/", SearchView.as_view(), name="search"),
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_catalog_api.py search_discovery/tests/test_search_api.py -q
```

Expected: new V1 catalog/search tests pass and legacy search tests remain green.

- [ ] **Step 7: Commit**

```powershell
git add backend/api/v1/catalog.py backend/api/v1/serializers.py backend/api/v1/urls.py backend/api/v1/tests/test_catalog_api.py
git commit -m "feat: add public catalog api v1"
```

---

### Task 5: Favorites And Reading Progress API

**Files:**
- Create: `backend/api/v1/user_library.py`
- Create: `backend/api/v1/tests/test_user_library_api.py`
- Modify: `backend/api/v1/urls.py`
- Modify: `backend/document_reader/admin.py`
- Modify: `backend/document_reader/models.py`
- Modify: `backend/document_reader/services.py`
- Add migration: `backend/document_reader/migrations/`

**Interfaces:**
- Produces `document_reader.models.FavoriteDocument`.
- Produces `document_reader.models.ReadingProgress`.
- Produces `favorite_document(user, document) -> tuple[FavoriteDocument, bool]`.
- Produces `remove_favorite(user, document) -> bool`.
- Produces `record_reading_progress(user, document, last_page_number: int) -> ReadingProgress`.
- Produces:
  - `GET /api/v1/me/favorites/`
  - `POST /api/v1/me/favorites/`
  - `DELETE /api/v1/me/favorites/{document_id}/`
  - `GET /api/v1/me/reading-progress/`
  - `PATCH /api/v1/me/reading-progress/{document_id}/`

- [ ] **Step 1: Write failing personal library tests**

Create `backend/api/v1/tests/test_user_library_api.py`:

```python
import pytest
from rest_framework.test import APIClient

from catalog.models import AcademicDomain, Document
from document_ingestion.models import DocumentVersion
from document_reader.models import FavoriteDocument, ReadingProgress


def auth_headers(client):
    response = client.post(
        "/api/v1/auth/register/",
        {"email": "reader@example.ga", "password": "StrongPass123!"},
        format="json",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {response.json()['tokens']['access']}"}


def create_document(slug="favorite-doc", access_model=Document.AccessModel.FREE):
    domain = AcademicDomain.objects.create(name=f"Domain {slug}", slug=f"domain-{slug}")
    document = Document.objects.create(
        title=f"Document {slug}",
        slug=slug,
        abstract="Resume public.",
        language_code="fr",
        publication_year=2026,
        academic_domain=domain,
        category=Document.Category.OPEN_RESOURCE,
        access_model=access_model,
        publication_status=Document.PublicationStatus.PUBLISHED,
    )
    DocumentVersion.objects.create(
        document=document,
        version_label="v1",
        status=DocumentVersion.Status.PROCESSED,
        is_current=True,
        page_count=10,
    )
    return document


@pytest.mark.django_db
def test_favorites_require_authentication():
    client = APIClient()

    response = client.get("/api/v1/me/favorites/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_add_favorite_is_idempotent():
    client = APIClient()
    headers = auth_headers(client)
    document = create_document()

    first = client.post("/api/v1/me/favorites/", {"document_id": document.pk}, format="json", **headers)
    second = client.post("/api/v1/me/favorites/", {"document_id": document.pk}, format="json", **headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert FavoriteDocument.objects.count() == 1


@pytest.mark.django_db
def test_list_favorites_returns_document_metadata():
    client = APIClient()
    headers = auth_headers(client)
    document = create_document()
    client.post("/api/v1/me/favorites/", {"document_id": document.pk}, format="json", **headers)

    response = client.get("/api/v1/me/favorites/", **headers)

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["document"]["id"] == document.pk


@pytest.mark.django_db
def test_delete_favorite_is_idempotent():
    client = APIClient()
    headers = auth_headers(client)
    document = create_document()

    response = client.delete(f"/api/v1/me/favorites/{document.pk}/", **headers)

    assert response.status_code == 204


@pytest.mark.django_db
def test_reading_progress_stores_resume_data_only():
    client = APIClient()
    headers = auth_headers(client)
    document = create_document()

    response = client.patch(
        f"/api/v1/me/reading-progress/{document.pk}/",
        {"last_page_number": 4},
        format="json",
        **headers,
    )

    assert response.status_code == 200
    progress = ReadingProgress.objects.get(document=document)
    assert progress.last_page_number == 4
    payload = response.json()
    assert set(payload) == {"document", "last_page_number", "updated_at"}
    assert "page_access" not in str(payload).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_user_library_api.py -q
```

Expected: FAIL because models and endpoints do not exist.

- [ ] **Step 3: Add personal library models**

Modify `backend/document_reader/models.py`:

```python
class FavoriteDocument(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_documents",
    )
    document = models.ForeignKey(
        "catalog.Document",
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "document"], name="uniq_favorite_document_per_user"),
        ]
        indexes = [
            models.Index(fields=["user", "created_at"], name="favorite_user_created_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} favorite {self.document}"


class ReadingProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reading_progress",
    )
    document = models.ForeignKey(
        "catalog.Document",
        on_delete=models.CASCADE,
        related_name="reading_progress",
    )
    last_page_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "document"], name="uniq_reading_progress_per_user_document"),
            models.CheckConstraint(condition=Q(last_page_number__gte=1), name="reading_progress_page_positive"),
        ]
        indexes = [
            models.Index(fields=["user", "updated_at"], name="reading_progress_user_time_idx"),
        ]
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.user} progress {self.document} page {self.last_page_number}"
```

Run:

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations document_reader
```

Expected: a migration creates `FavoriteDocument` and `ReadingProgress`.

- [ ] **Step 4: Add personal library services**

Extend `backend/document_reader/services.py`:

```python
from document_reader.models import FavoriteDocument, ReadingProgress


def favorite_document(user, document: Document) -> tuple[FavoriteDocument, bool]:
    if not document_is_reader_accessible(document):
        raise ReaderAccessDenied("Document is not discoverable")
    return FavoriteDocument.objects.get_or_create(user=user, document=document)


def remove_favorite(user, document: Document) -> bool:
    deleted_count, _ = FavoriteDocument.objects.filter(user=user, document=document).delete()
    return deleted_count > 0


def record_reading_progress(user, document: Document, last_page_number: int) -> ReadingProgress:
    if last_page_number < 1:
        raise ReaderPageUnavailable("last_page_number must be positive")
    if not user_can_read_document(user, document):
        raise ReaderAccessDenied("User cannot record progress for this document")
    version = get_current_processed_version(document)
    if last_page_number > version.page_count:
        raise ReaderPageUnavailable("last_page_number is outside the readable document range")
    progress, _ = ReadingProgress.objects.update_or_create(
        user=user,
        document=document,
        defaults={"last_page_number": last_page_number},
    )
    return progress
```

- [ ] **Step 5: Register models in admin**

Modify `backend/document_reader/admin.py`:

```python
from document_reader.models import FavoriteDocument, PageAccessLog, ReaderSession, ReadingProgress


@admin.register(FavoriteDocument)
class FavoriteDocumentAdmin(admin.ModelAdmin):
    list_display = ["user", "document", "created_at"]
    search_fields = ["user__email", "document__title"]
    list_filter = ["created_at"]


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "document", "last_page_number", "updated_at"]
    search_fields = ["user__email", "document__title"]
    list_filter = ["updated_at"]
```

Keep existing `ReaderSessionAdmin` and `PageAccessLogAdmin` registrations.

- [ ] **Step 6: Implement personal library API views**

Create `backend/api/v1/user_library.py`:

```python
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from api.v1.errors import error_response
from api.v1.pagination import StandardResultsSetPagination
from api.v1.serializers import serialize_document_metadata
from catalog.models import Document
from document_reader.exceptions import ReaderAccessDenied, ReaderPageUnavailable
from document_reader.models import FavoriteDocument, ReadingProgress
from document_reader.services import favorite_document, record_reading_progress, remove_favorite


class FavoriteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favorites = FavoriteDocument.objects.select_related(
            "document", "document__academic_domain", "document__owner_organization"
        ).filter(
            user=request.user,
            document__publication_status=Document.PublicationStatus.PUBLISHED,
        ).exclude(document__access_model=Document.AccessModel.PRIVATE)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(favorites, request, view=self)
        return paginator.get_paginated_response(
            [
                {
                    "document": serialize_document_metadata(favorite.document, user=request.user),
                    "created_at": favorite.created_at.isoformat(),
                }
                for favorite in page
            ]
        )

    def post(self, request):
        document_id = request.data.get("document_id")
        try:
            document = Document.objects.get(pk=document_id)
        except (TypeError, ValueError, Document.DoesNotExist):
            return error_response("not_found", "Document not found.", status.HTTP_404_NOT_FOUND)
        try:
            favorite, created = favorite_document(request.user, document)
        except ReaderAccessDenied:
            return error_response("not_found", "Document not found.", status.HTTP_404_NOT_FOUND)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            {
                "document": serialize_document_metadata(favorite.document, user=request.user),
                "created_at": favorite.created_at.isoformat(),
            },
            status=status_code,
        )


class FavoriteDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, document_id: int):
        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        remove_favorite(request.user, document)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadingProgressListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        progress_rows = ReadingProgress.objects.select_related(
            "document", "document__academic_domain", "document__owner_organization"
        ).filter(
            user=request.user,
            document__publication_status=Document.PublicationStatus.PUBLISHED,
        ).exclude(document__access_model=Document.AccessModel.PRIVATE)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(progress_rows, request, view=self)
        return paginator.get_paginated_response(
            [
                {
                    "document": serialize_document_metadata(progress.document, user=request.user),
                    "last_page_number": progress.last_page_number,
                    "updated_at": progress.updated_at.isoformat(),
                }
                for progress in page
            ]
        )


class ReadingProgressUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, document_id: int):
        try:
            page_number = int(request.data.get("last_page_number"))
        except (TypeError, ValueError):
            return error_response(
                "invalid_page_number",
                "last_page_number must be a positive integer.",
                status.HTTP_400_BAD_REQUEST,
            )
        try:
            document = Document.objects.get(pk=document_id)
            progress = record_reading_progress(request.user, document, page_number)
        except Document.DoesNotExist:
            return error_response("not_found", "Document not found.", status.HTTP_404_NOT_FOUND)
        except ReaderPageUnavailable:
            return error_response("invalid_page_number", "last_page_number must be positive.", status.HTTP_400_BAD_REQUEST)
        except ReaderAccessDenied:
            return error_response("entitlement_required", "An active read entitlement is required.", status.HTTP_403_FORBIDDEN)
        return Response(
            {
                "document": serialize_document_metadata(progress.document, user=request.user),
                "last_page_number": progress.last_page_number,
                "updated_at": progress.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
```

- [ ] **Step 7: Route personal library endpoints**

Modify `backend/api/v1/urls.py`:

```python
from api.v1.user_library import (
    FavoriteDeleteView,
    FavoriteListCreateView,
    ReadingProgressListView,
    ReadingProgressUpdateView,
)

urlpatterns += [
    path("me/favorites/", FavoriteListCreateView.as_view(), name="favorite-list-create"),
    path("me/favorites/<int:document_id>/", FavoriteDeleteView.as_view(), name="favorite-delete"),
    path("me/reading-progress/", ReadingProgressListView.as_view(), name="reading-progress-list"),
    path(
        "me/reading-progress/<int:document_id>/",
        ReadingProgressUpdateView.as_view(),
        name="reading-progress-update",
    ),
]
```

- [ ] **Step 8: Run tests**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_user_library_api.py document_reader/tests -q
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Expected: personal library tests pass, document reader tests pass, and migrations are committed.

- [ ] **Step 9: Commit**

```powershell
git add backend/api/v1/user_library.py backend/api/v1/urls.py backend/api/v1/tests/test_user_library_api.py backend/document_reader/models.py backend/document_reader/services.py backend/document_reader/admin.py backend/document_reader/migrations
git commit -m "feat: add personal library api"
```

---

### Task 6: OpenAPI Coverage And Final API Verification

**Files:**
- Create: `backend/api/v1/tests/test_openapi_schema.py`
- Modify: `backend/api/v1/auth.py`
- Modify: `backend/api/v1/catalog.py`
- Modify: `backend/api/v1/reader.py`
- Modify: `backend/api/v1/user_library.py`
- Modify: `backend/api/v1/views.py`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes all endpoints from Tasks 1-5.
- Produces OpenAPI coverage for every public V1 endpoint.
- Documents API dependency and verification commands for contributors.

- [ ] **Step 1: Write failing OpenAPI coverage tests**

Create `backend/api/v1/tests/test_openapi_schema.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail where schema annotations are missing**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests/test_openapi_schema.py -q
```

Expected: FAIL if schema paths, path parameters, or bearer auth metadata are incomplete.

- [ ] **Step 3: Add explicit OpenAPI annotations**

In each API view module, import drf-spectacular helpers:

```python
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
```

Add `@extend_schema` to every public view method. Place this decorator immediately before `RegisterView.post`:

```python
@extend_schema(
    summary="Register an individual learner account",
    request=RegisterSerializer,
    responses={
        201: OpenApiResponse(description="User created with JWT tokens"),
        400: OpenApiResponse(description="Invalid registration data"),
        409: OpenApiResponse(description="Email already exists"),
    },
    examples=[
        OpenApiExample(
            "Successful registration",
            value={
                "user": {
                    "id": 1,
                    "email": "reader@example.ga",
                    "display_name": "Reader One",
                    "account_type": "individual",
                },
                "tokens": {"access": "<jwt>", "refresh": "<jwt>"},
            },
            response_only=True,
        )
    ],
)
```

For reader endpoints, include descriptions that state:

```text
Free documents allow anonymous controlled reader sessions. Restricted documents require JWT authentication and active read entitlement.
```

For catalog/search endpoints, include descriptions that state:

```text
Responses expose public metadata only and never include raw files, storage keys, signed URLs, or OCR full text.
```

- [ ] **Step 4: Document API verification commands**

Update `AGENTS.md` command section with:

```markdown
- `.\.venv\Scripts\python.exe -m pytest api/v1/tests -q`: run the public API V1 tests.
- `.\.venv\Scripts\python.exe manage.py spectacular --file schema.yml`: export the OpenAPI schema.
```

- [ ] **Step 5: Run API and schema tests**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest api/v1/tests -q
.\.venv\Scripts\python.exe manage.py spectacular --file schema.yml
Remove-Item -LiteralPath schema.yml
```

Expected: API tests pass, `schema.yml` is generated, and the generated schema file is removed before commit because this slice tracks code and tests only.

- [ ] **Step 6: Run full verification**

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate
```

Run from repo root:

```powershell
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit**

```powershell
git add backend/api/v1 AGENTS.md
git commit -m "docs: complete api v1 schema coverage"
```
