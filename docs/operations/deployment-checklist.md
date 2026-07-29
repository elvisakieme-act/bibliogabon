# Deployment Checklist

## Pre-Deploy

- Confirm `DJANGO_ENV=production`.
- Confirm `DJANGO_DEBUG=False`.
- Confirm `DJANGO_SECRET_KEY` is a production secret and is not committed.
- Confirm `DJANGO_ALLOWED_HOSTS` contains the production domain.
- Confirm `DJANGO_CSRF_TRUSTED_ORIGINS` contains the HTTPS origin.
- Confirm secure cookie and SSL redirect variables are enabled.
- Confirm `DATABASE_URL` points to the production PostgreSQL database.
- Confirm private document storage credentials are configured outside Git.

## Verification Commands

Run from `backend/` before release:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Run on the deployment target:

```powershell
python manage.py migrate
python manage.py check --deploy
```

## Smoke Checks

- Request `/health/` and confirm HTTP 200.
- Sign in to Django Admin with a staff account.
- Open one published free document in the reader.
- Run one search query that should return a known published document.
- Confirm new errors are not appearing in application logs.

## Rollback

- Stop the new application process.
- Restore the previous application release directory or service image.
- Repoint the process manager to the previous release.
- Run `/health/` after rollback.
- Record the rollback reason, timestamp, operator, and follow-up action in the incident log.
