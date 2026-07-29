from __future__ import annotations


VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def build_logging_config(log_level: str) -> dict:
    normalized = (log_level or "INFO").strip().upper()
    if normalized not in VALID_LOG_LEVELS:
        normalized = "INFO"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": normalized,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": normalized,
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": normalized,
                "propagate": False,
            },
        },
    }
