"""Charge l'application Celery au démarrage de Django, pour que le
décorateur `shared_task` s'y rattache."""

from config.celery import celery_app

__all__ = ("celery_app",)
