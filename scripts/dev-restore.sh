#!/usr/bin/env bash
#
# Remonter l'environnement de développement après une réinitialisation du
# studio.
#
# Le studio Lightning efface `node_modules` et le cluster PostgreSQL sans
# toucher au dépôt ni à `backend/private-media/` : les PDF sources survivent,
# le reste est à refaire. La manœuvre a coûté une vingtaine de minutes à chaque
# fois, et une erreur silencieuse — voir SIGPIPE plus bas — a déjà fait croire
# à une base peuplée qui ne l'était pas.
#
#   bash scripts/dev-restore.sh            # tout
#   bash scripts/dev-restore.sh --no-pdf   # sans ré-ingestion (plus rapide)
#
set -euo pipefail

racine="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
avec_pdf=1
[[ "${1:-}" == "--no-pdf" ]] && avec_pdf=0

echo "→ PostgreSQL"
sudo service postgresql start >/dev/null 2>&1 || true
until pg_isready -q; do sleep 1; done

cd "$racine/backend"
if ! sudo -u postgres psql -tAc "select 1 from pg_database where datname='bibliogabon'" | grep -q 1; then
  echo "→ rôle et base (mot de passe lu dans backend/.env, jamais affiché)"
  # Le SQL passe par un fichier temporaire que l'on efface : écrit sur la ligne
  # de commande, le mot de passe serait visible de tout le système par `ps`.
  sql="$(mktemp)"
  trap 'rm -f "$sql"' EXIT
  python3 - "$sql" <<'PY'
import re, sys, urllib.parse
from pathlib import Path

url = urllib.parse.urlparse(
    re.search(r"^DATABASE_URL=(.+)$", Path(".env").read_text(), re.M).group(1).strip().strip('"')
)
user = urllib.parse.unquote(url.username or "")
password = urllib.parse.unquote(url.password or "").replace("'", "''")
name = (url.path or "").lstrip("/")
# CREATEDB : la suite de tests crée sa propre base.
Path(sys.argv[1]).write_text(
    f'CREATE ROLE "{user}" LOGIN CREATEDB PASSWORD \'{password}\';\n'
    f'CREATE DATABASE "{name}" OWNER "{user}" ENCODING \'UTF8\';\n'
)
PY
  sudo -u postgres psql -v ON_ERROR_STOP=1 < "$sql"
  rm -f "$sql"
  trap - EXIT
fi

echo "→ migrations"
python manage.py migrate --no-input >/dev/null

echo "→ jeu de démonstration"
# **Jamais `| head`** : la commande est longue, et SIGPIPE la tue au milieu de
# sa transaction. Le résumé s'affiche avant le commit, donc tout a l'air
# d'avoir réussi — et la base est vide. C'est arrivé.
python manage.py seed_demo >/dev/null

if [[ "$avec_pdf" == 1 ]]; then
  echo "→ ingestion des PDF retrouvés dans private-media"
  # Les paires passent par un fichier et non par un tube : un `while read` qui
  # appelle une commande Django lui laisse consommer son entrée standard, et la
  # boucle s'arrête après le premier tour. `--no-imports` fait taire la bannière
  # du shell Django, qui atterrissait sinon dans la première paire.
  paires="$(mktemp)"
  trap 'rm -f "$paires"' EXIT
  python manage.py shell --no-imports -c '
from pathlib import Path
from catalog.models import Document

# Les identifiants se décalent à chaque recréation de la base : on apparie donc
# par ordre, et non par numéro de dossier.
documents = list(Document.objects.order_by("id"))
dossiers = sorted(
    (d for d in Path("private-media/documents").iterdir() if d.is_dir()),
    key=lambda d: int(d.name),
)
for document, dossier in zip(documents, dossiers):
    pdf = next(iter(sorted(dossier.rglob("*.pdf"))), None)
    if pdf:
        print(f"{document.id}\t{pdf}")
' > "$paires"
  while IFS=$'\t' read -r id pdf; do
    [[ -n "${id:-}" ]] || continue
    echo "   document $id"
    python manage.py ingest_file "$id" "$pdf" --replace >/dev/null </dev/null
  done < "$paires"
  rm -f "$paires"
  trap - EXIT
fi

echo "→ dépendances du frontend"
cd "$racine/frontend"
export PATH="$HOME/.nvm/versions/node/v22.23.2/bin:$PATH"
[[ -d node_modules ]] || npm ci >/dev/null

echo
echo "Prêt. Les deux serveurs se lancent détachés — sinon ils meurent avec le shell :"
echo "  (cd backend && setsid nohup python manage.py runserver 0.0.0.0:8002 --noreload >/tmp/backend.log 2>&1 &)"
echo "  (cd frontend && setsid nohup npm run dev >/tmp/vite.log 2>&1 &)"
