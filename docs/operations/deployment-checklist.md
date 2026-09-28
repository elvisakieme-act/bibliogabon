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
- **SeaweedFS is the chosen store (D016), self-hosted.** Its operation is on us,
  not a provider: before first service, confirm that the volume servers are
  replicated, that `weed backup` or a filesystem-level snapshot runs on the
  same schedule as the database backup, and that free capacity is monitored.
  Page rendering produces roughly 150 objects per document, so object *count*
  grows far faster than byte volume — a filer that runs out of metadata room
  fails writes while disk space still looks ample.
- Confirm the S3 gateway is reachable from the application host and that
  `DOCUMENT_STORAGE_ENDPOINT_URL` points at it. Production refuses to start on
  the filesystem backend, so a misconfigured endpoint fails loudly at boot
  rather than silently writing nowhere.
- Confirm `CELERY_BROKER_URL` points to the production Redis instance; the
  application refuses to start in production without it.
- Confirm `DOCUMENT_STORAGE_BACKEND=s3` with endpoint and credentials set;
  production refuses the filesystem backend.
- Confirm at least one Celery worker is running, and that the host has
  `tesseract-ocr` and `tesseract-ocr-fra` installed for OCR.

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

- Request `GET /health/` and confirm HTTP 200. The health probe is GET-only.
- Sign in to Django Admin with a staff account.
- Open one published free document in the reader.
- Run one search query that should return a known published document.
- Confirm new errors are not appearing in application logs.

## Rollback

Migration `document_reader.0004_alter_pageaccesslog_page` cannot be reversed
once any document has been re-ingested with `--replace`: access logs survive
their deleted page with a null reference, and restoring the NOT NULL
constraint has no data to restore. Roll back the application release, not
that migration.


- Stop the new application process.
- Restore the previous application release directory or service image.
- Repoint the process manager to the previous release.
- Run `/health/` after rollback.
- Record the rollback reason, timestamp, operator, and follow-up action in the incident log.
