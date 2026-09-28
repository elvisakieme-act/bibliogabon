"""Greffon pytest chargé avant tout le reste.

Les tests ne doivent **jamais** dépendre du `backend/.env` d'un développeur.
Ce fichier n'est pas versionné : s'il influençait la suite, celle-ci se
comporterait différemment sur chaque machine et en intégration continue, où il
n'existe pas — exactement la divergence qui a laissé la CI rouge pendant
vingt-huit exécutions pendant que tout passait en local.

Pourquoi un greffon et non un `conftest.py` : `pytest-django` initialise Django
dans `pytest_load_initial_conftests`, **avant** l'import du `conftest.py`
racine. Une variable posée là arriverait après la lecture des réglages, et
n'aurait aucun effet — ce qui a été observé avant d'écrire ceci.

`setdefault` : une variable explicitement posée avant l'appel à pytest reste
prioritaire, pour qui veut délibérément tester contre un fichier donné.
"""

import os

import pytest

os.environ.setdefault("DJANGO_ENV_FILE", "")


def pytest_configure(config):
    """Refuse de valider le produit contre une base qui n'est pas la sienne.

    Le `.env` étant neutralisé ci-dessus, `DATABASE_URL` doit être une vraie
    variable d'environnement — sinon la suite retombe sur SQLite **sans rien
    dire**, et c'est exactement ce qui est arrivé : 862 tests annoncés verts
    « sur PostgreSQL » alors qu'ils tournaient sur SQLite, pendant qu'une
    requête refusée par PostgreSQL (`FOR UPDATE` sur le côté nullable d'une
    jointure externe) cassait l'activation d'un abonnement en production.

    SQLite ignore purement et simplement `select_for_update`, et son verrou
    global sérialise les écritures : il masque donc deux classes entières de
    défauts — les requêtes qu'il accepte et que PostgreSQL refuse, et les
    courses entre requêtes concurrentes.

    Même esprit que `REQUIRE_OCR` : un écart silencieux vaut moins qu'un échec
    bruyant. `ALLOW_SQLITE_TESTS=1` reste possible pour une vérification
    rapide, mais il faut alors l'écrire, donc le savoir.
    """
    from django.conf import settings

    engine = settings.DATABASES["default"]["ENGINE"]
    if engine.endswith("sqlite3") and not os.getenv("ALLOW_SQLITE_TESTS"):
        raise pytest.UsageError(
            "La suite tournerait sur SQLite, qui n'est pas la base du produit.\n"
            "SQLite accepte des requêtes que PostgreSQL refuse et sérialise les "
            "écritures : il masque les défauts de production au lieu de les "
            "montrer.\n\n"
            "  export DATABASE_URL=postgres://bibliogabon:...@127.0.0.1:5432/bibliogabon\n\n"
            "Pour une vérification rapide malgré tout : ALLOW_SQLITE_TESTS=1"
        )
