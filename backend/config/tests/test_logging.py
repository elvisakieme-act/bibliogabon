from pathlib import Path

from config.logconfig import build_logging_config


def test_build_logging_config_uses_requested_level():
    config = build_logging_config("DEBUG")

    assert config["handlers"]["console"]["level"] == "DEBUG"
    assert config["root"]["level"] == "DEBUG"
    assert config["formatters"]["standard"]["format"] == "%(asctime)s %(levelname)s %(name)s %(message)s"


def test_build_logging_config_falls_back_to_info_for_blank_level():
    config = build_logging_config("")

    assert config["root"]["level"] == "INFO"


def test_env_example_documents_launch_hardening_variables():
    env_example = Path(__file__).resolve().parents[2] / ".env.example"
    text = env_example.read_text(encoding="utf-8")

    required_names = [
        "DJANGO_ENV=",
        "DJANGO_SECRET_KEY=",
        "DJANGO_DEBUG=",
        "DJANGO_ALLOWED_HOSTS=",
        "DJANGO_CSRF_TRUSTED_ORIGINS=",
        "DJANGO_SECURE_SSL_REDIRECT=",
        "DJANGO_SESSION_COOKIE_SECURE=",
        "DJANGO_CSRF_COOKIE_SECURE=",
        "DJANGO_LOG_LEVEL=",
        "DATABASE_URL=",
        "DOCUMENT_STORAGE_BUCKET=",
        "DOCUMENT_STORAGE_KEY_PREFIX=",
        "READER_SESSION_TTL_MINUTES=",
    ]
    for name in required_names:
        assert name in text
