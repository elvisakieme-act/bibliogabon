"""Application Celery de BiblioGABON.

La configuration vient des réglages Django préfixés `CELERY_`, de sorte
qu'il n'existe qu'une seule source de vérité : `config/settings.py`.

En développement et en test, `CELERY_TASK_ALWAYS_EAGER` est vrai : les
tâches s'exécutent en ligne et la suite tourne sans broker.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

celery_app = Celery("bibliogabon")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")
celery_app.autodiscover_tasks()
