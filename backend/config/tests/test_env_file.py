"""Le fichier `backend/.env` doit être lu.

Il ne l'était pas : les réglages n'appelaient que `os.getenv`, et rien ne
chargeait le fichier. Le README demandait pourtant de le créer — vrai pour
Vite, qui lit `.env` nativement, faux pour Django. Toute la configuration
locale y était donc écrite sans effet, et un symptôme de CORS envoyait
chercher le défaut à l'opposé de sa cause.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

PROBE = textwrap.dedent(
    """
    import os, django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    from django.conf import settings
    print(",".join(settings.ALLOWED_HOSTS))
    """
)


def run_probe(env: dict[str, str] | None = None) -> str:
    """Un sous-processus est nécessaire : les réglages sont lus une fois par
    interpréteur, et le test doit observer ce qui se passe au démarrage.

    Les variables `DJANGO_*` de l'environnement parent sont **retirées** : le
    processus de test a lui-même chargé le fichier via `load_dotenv`, qui écrit
    dans `os.environ`, et elles écraseraient donc silencieusement ce que le
    test cherche à observer.
    """
    child = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
    child["PYTHONPATH"] = str(BACKEND)
    child.update(env or {})
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=BACKEND,
        env=child,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_the_env_file_is_read():
    env_file = BACKEND / ".env"
    original = env_file.read_text(encoding="utf-8") if env_file.is_file() else None
    marker = "hote-temoin-du-fichier-env.example"
    try:
        env_file.write_text(
            f"DJANGO_ENV=development\nDJANGO_ALLOWED_HOSTS=localhost,{marker}\n",
            encoding="utf-8",
        )
        hosts = run_probe()
        assert marker in hosts, (
            "backend/.env n'est pas lu : la configuration locale que le README "
            "demande de créer resterait sans effet"
        )
    finally:
        if original is None:
            env_file.unlink(missing_ok=True)
        else:
            env_file.write_text(original, encoding="utf-8")


def test_a_real_environment_variable_wins_over_the_file():
    """En CI et en production la configuration vient de l'orchestrateur, pas
    d'un fichier sur disque : le fichier ne doit jamais l'écraser."""
    env_file = BACKEND / ".env"
    original = env_file.read_text(encoding="utf-8") if env_file.is_file() else None
    try:
        env_file.write_text(
            "DJANGO_ENV=development\nDJANGO_ALLOWED_HOSTS=depuis-le-fichier.example\n",
            encoding="utf-8",
        )
        hosts = run_probe({"DJANGO_ALLOWED_HOSTS": "depuis-l-environnement.example"})
        assert "depuis-l-environnement.example" in hosts
        assert "depuis-le-fichier.example" not in hosts
    finally:
        if original is None:
            env_file.unlink(missing_ok=True)
        else:
            env_file.write_text(original, encoding="utf-8")


def test_the_settings_load_without_an_env_file():
    """Un dépôt fraîchement cloné n'a pas de `.env` : l'absence du fichier ne
    doit pas empêcher le démarrage."""
    env_file = BACKEND / ".env"
    original = env_file.read_text(encoding="utf-8") if env_file.is_file() else None
    try:
        env_file.unlink(missing_ok=True)
        hosts = run_probe()
        assert "localhost" in hosts
    finally:
        if original is not None:
            env_file.write_text(original, encoding="utf-8")


def test_an_explicit_empty_env_file_loads_nothing():
    """`DJANGO_ENV_FILE=""` fait tourner le processus sur la seule
    configuration externe, même si un `.env` traîne sur le disque. C'est ce
    qui permet d'observer la configuration par défaut, et ce dont un
    déploiement a besoin quand sa configuration vient de l'orchestrateur."""
    env_file = BACKEND / ".env"
    original = env_file.read_text(encoding="utf-8") if env_file.is_file() else None
    try:
        env_file.write_text(
            "DJANGO_ENV=development\nDJANGO_ALLOWED_HOSTS=depuis-le-fichier.example\n",
            encoding="utf-8",
        )
        hosts = run_probe({"DJANGO_ENV_FILE": ""})
        assert "depuis-le-fichier.example" not in hosts
        assert "localhost" in hosts
    finally:
        if original is None:
            env_file.unlink(missing_ok=True)
        else:
            env_file.write_text(original, encoding="utf-8")


def test_an_explicit_env_file_path_is_honoured(tmp_path):
    other = tmp_path / "autre.env"
    other.write_text(
        "DJANGO_ENV=development\nDJANGO_ALLOWED_HOSTS=depuis-l-autre-fichier.example\n",
        encoding="utf-8",
    )

    hosts = run_probe({"DJANGO_ENV_FILE": str(other)})

    assert "depuis-l-autre-fichier.example" in hosts
