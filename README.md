# BiblioGABON

Plateforme de bibliothèque numérique académique nationale pour le Gabon : catalogue, lecteur sécurisé, entitlements/abonnements, recherche, et reporting institutionnel.

## Stack

- **Backend** : Django 5 / Django REST Framework, JWT (`djangorestframework-simplejwt`), OpenAPI via `drf-spectacular`. PostgreSQL en production, SQLite en local.
- **Frontend** : React 19, Vite, TanStack Router/Query, Tailwind CSS.
- **Cible future** (voir `docs/technical/00-subsystem-plan-index.md`) : Redis + Celery pour les jobs asynchrones, stockage objet S3-compatible pour les documents privés.

## Structure du dépôt

```
backend/    Projet Django (apps : accounts, catalog, document_ingestion,
            document_processing, document_reader, search_discovery,
            billing, operations, analytics, api/v1)
frontend/   Application web React (côté lecteur)
docs/       Specs techniques, plans produit, runbooks opérationnels
```

## Setup backend

Prérequis : Python 3.12+.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
copy .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

`requirements-lock.txt` fixe des versions exactes pour un environnement reproductible ; `pyproject.toml` reste la source des plages de versions acceptées. Pour régénérer le lock après un changement de dépendances, voir l'en-tête de `backend/requirements-lock.txt`.

Le serveur local par défaut utilise SQLite (`backend/db.sqlite3`, non versionné). Pour PostgreSQL, définir `DATABASE_URL` dans `.env` (voir `backend/.env.example`).

### Tests et vérifications backend

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest api/v1/tests -q   # API publique uniquement
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

### Documentation API

Une fois le serveur lancé : `http://127.0.0.1:8000/api/docs/` (Swagger UI) et `http://127.0.0.1:8000/api/v1/schema/` (schéma OpenAPI brut).

## Setup frontend

Prérequis : Node.js 20+.

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

### Tests et vérifications frontend

```bash
cd frontend
npm run test    # tests unitaires (vitest)
npm run lint    # eslint
npm run build   # type-check (tsc) + build de production
```

## Documentation complémentaire

- `docs/technical/00-subsystem-plan-index.md` : direction technique et concepts de domaine partagés.
- `docs/operations/` : runbooks (sauvegarde/restauration, réponse aux incidents, checklist de déploiement).
- `AGENTS.md` : conventions de code, de commit et de PR pour ce dépôt.

## État du projet

Le backend couvre le modèle de données et la logique métier (identité, catalogue, entitlements, lecteur sécurisé, facturation, opérations, analytics) avec une suite de tests par app. Le pipeline de stockage réel des fichiers (upload, S3, jobs asynchrones Celery/Redis, OCR) est modélisé mais pas encore implémenté — voir `document_ingestion/` et `document_processing/`.
