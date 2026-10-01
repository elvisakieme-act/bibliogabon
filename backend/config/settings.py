import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from config.env import (
    DEFAULT_DEVELOPMENT_SECRET_KEY,
    env_bool,
    env_int,
    env_list,
    validate_django_env,
    validate_document_storage_backend,
    validate_production_pipeline_settings,
    validate_production_settings,
)
from config.logconfig import build_logging_config

BASE_DIR = Path(__file__).resolve().parent.parent

# `backend/.env` est lu avant toute lecture de variable.
#
# Il ne l'était pas : les réglages n'appelaient que `os.getenv`, et rien ne
# chargeait le fichier. Le README demandait pourtant de le créer — vrai pour
# Vite, qui lit `.env` nativement, faux pour Django. Toute la configuration
# locale y était donc écrite sans effet, et le diagnostic partait ailleurs.
#
# `override=False` : une vraie variable d'environnement l'emporte toujours sur
# le fichier. C'est ce qui doit se passer en CI et en production, où la
# configuration vient de l'orchestrateur et non d'un fichier sur disque.
#
# `DJANGO_ENV_FILE` désigne un autre fichier, et **vide** n'en charge aucun —
# de quoi observer la configuration par défaut, ou faire tourner un processus
# sur une configuration entièrement externe alors qu'un `.env` traîne sur le
# disque.
_env_file = os.getenv("DJANGO_ENV_FILE")
if _env_file is None:
    load_dotenv(BASE_DIR / ".env", override=False)
elif _env_file.strip():
    load_dotenv(_env_file, override=False)

DJANGO_ENV = validate_django_env(os.getenv("DJANGO_ENV", "development"))
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEFAULT_DEVELOPMENT_SECRET_KEY)
DEBUG = env_bool("DJANGO_DEBUG", default=DJANGO_ENV != "production")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1")

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

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.cors.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CSRF_FAILURE_VIEW = "document_reader.views.csrf_failure"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DJANGO_ENV == "production" and not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL is required in production")

# Connexions persistantes **hors** du serveur de développement seulement.
#
# `runserver` crée un fil par requête et ne le réutilise pas : une connexion
# gardée 60 secondes reste donc ouverte pour un fil déjà mort. En ouvrant un
# document de 157 pages, dont le lecteur demande les images par rafales, les
# 100 connexions de PostgreSQL ont été épuisées en une minute — et le symptôme
# était une erreur 500 sur le *catalogue*, à l'autre bout de l'application.
# En production, un serveur à processus fixes les réutilise vraiment, et c'est
# là qu'elles valent leur prix.
CONN_MAX_AGE = 0 if DJANGO_ENV == "development" else 60

DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=CONN_MAX_AGE,
    )
}

# SQLite en développement : le lecteur tuilé demande des dizaines d'images en
# parallèle, et le mode par défaut verrouille la base entière dès qu'une
# écriture est en cours. Le symptôme est une erreur 500 sur une tuile, ce qui
# envoie la recherche du défaut vers le tuilage — qui n'y est pour rien.
#
# WAL laisse les lectures se poursuivre pendant une écriture ; le délai
# d'attente couvre le cas où plusieurs premières tuiles d'une même page
# arrivent ensemble. Sans effet en production, qui tourne sur PostgreSQL.
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    DATABASES["default"].setdefault("OPTIONS", {}).update(
        {"timeout": 20, "init_command": "PRAGMA journal_mode=WAL;"}
    )

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Libreville"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DOCUMENT_STORAGE_BUCKET = os.getenv("DOCUMENT_STORAGE_BUCKET", "bibliogabon-private-documents")
DOCUMENT_STORAGE_KEY_PREFIX = os.getenv("DOCUMENT_STORAGE_KEY_PREFIX", "documents")
READER_SESSION_TTL_MINUTES = env_int("READER_SESSION_TTL_MINUTES", 120)
# Adresse publique de l'API, quand elle diffère de ce que Django voit.
#
# Le manifeste IIIF doit annoncer des adresses absolues — la spécification les
# exige — et un visualiseur construit **toutes** ses requêtes à partir
# d'elles. Derrière un proxy inverse, `build_absolute_uri` rend l'adresse
# interne : le manifeste s'affiche normalement et pas une seule image ne
# charge, ce qui envoie la recherche du défaut au mauvais endroit.
#
# Vide, l'adresse est déduite de la requête, ce qui est juste en développement
# et en accès direct.
PUBLIC_API_BASE_URL = os.getenv("DJANGO_PUBLIC_API_BASE_URL", "").rstrip("/")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = env_list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    default="http://127.0.0.1:5173,http://localhost:5173",
)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=DJANGO_ENV == "production")
SESSION_COOKIE_SECURE = env_bool(
    "DJANGO_SESSION_COOKIE_SECURE", default=DJANGO_ENV == "production"
)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", default=DJANGO_ENV == "production")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

validate_production_settings(
    django_env=DJANGO_ENV,
    debug=DEBUG,
    secret_key=SECRET_KEY,
    allowed_hosts=ALLOWED_HOSTS,
    csrf_trusted_origins=CSRF_TRUSTED_ORIGINS,
    secure_ssl_redirect=SECURE_SSL_REDIRECT,
    session_cookie_secure=SESSION_COOKIE_SECURE,
    csrf_cookie_secure=CSRF_COOKIE_SECURE,
)
# --- Pilier d'ingestion : file de traitement et stockage objet ---------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "").strip()
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "").strip() or CELERY_BROKER_URL
# En developpement et en test, les taches s'executent en ligne : la suite
# tourne sans broker.
CELERY_TASK_ALWAYS_EAGER = env_bool(
    "CELERY_TASK_ALWAYS_EAGER",
    default=DJANGO_ENV != "production",
)
CELERY_TASK_EAGER_PROPAGATES = CELERY_TASK_ALWAYS_EAGER

DOCUMENT_STORAGE_BACKEND = validate_document_storage_backend(
    os.getenv("DOCUMENT_STORAGE_BACKEND", "filesystem")
)
DOCUMENT_STORAGE_ENDPOINT_URL = os.getenv("DOCUMENT_STORAGE_ENDPOINT_URL", "").strip()
DOCUMENT_STORAGE_ACCESS_KEY = os.getenv("DOCUMENT_STORAGE_ACCESS_KEY", "").strip()
DOCUMENT_STORAGE_SECRET_KEY = os.getenv("DOCUMENT_STORAGE_SECRET_KEY", "").strip()
# boto3 exige une region, meme quand le fournisseur S3-compatible l'ignore.
DOCUMENT_STORAGE_REGION = os.getenv("DOCUMENT_STORAGE_REGION", "").strip() or "us-east-1"

# 300 ppp pour une A4 — la norme d'archivage pour du texte. Le tuilage IIIF
# rend ce choix peu coûteux pour le lecteur, qui ne télécharge que les tuiles
# qu'il regarde : mesuré à 249 ko stockés par page, contre ~40 ko téléchargés
# pour voir une page entière avant le tuilage. Changer cette valeur oblige à
# réingérer : les tuiles et leur `info.json` en dépendent.
DOCUMENT_PAGE_IMAGE_WIDTH = env_int("DOCUMENT_PAGE_IMAGE_WIDTH", 2480)
OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "").strip() or "fra"
OCR_MIN_CHARACTERS = env_int("OCR_MIN_CHARACTERS", 20)

# Dépôt : bornes vérifiées avant toute écriture en stockage.
DOCUMENT_UPLOAD_MAX_BYTES = env_int("DOCUMENT_UPLOAD_MAX_BYTES", 200 * 1024 * 1024)
DOCUMENT_UPLOAD_ACCEPTED_MIME_TYPES = env_list(
    "DOCUMENT_UPLOAD_ACCEPTED_MIME_TYPES", default="application/pdf"
)

validate_production_pipeline_settings(
    django_env=DJANGO_ENV,
    celery_broker_url=CELERY_BROKER_URL,
    document_storage_backend=DOCUMENT_STORAGE_BACKEND,
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGGING = build_logging_config(os.getenv("DJANGO_LOG_LEVEL", "INFO"))

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PARSER_CLASSES": ("rest_framework.parsers.JSONParser",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
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
