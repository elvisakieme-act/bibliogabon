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

os.environ.setdefault("DJANGO_ENV_FILE", "")
