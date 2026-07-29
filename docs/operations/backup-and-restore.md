# Backup And Restore Runbook

## Scope

BiblioGABON launch backups cover PostgreSQL data and S3-compatible private document storage. Backups must be encrypted at rest and access must be limited to operators who can restore service.

## PostgreSQL Backup

Run a manual logical backup before risky releases:

```bash
pg_dump "$DATABASE_URL" --format=custom --file="backup-$(date +%Y%m%d-%H%M%S).dump"
```

Store the dump outside the application server and record the backup filename, timestamp, database name, and operator.

## PostgreSQL Restore

Restore into a clean database first:

```bash
createdb bibliogabon_restore_test
pg_restore --dbname=bibliogabon_restore_test backup-file.dump
psql --dbname=bibliogabon_restore_test -c "select count(*) from django_migrations;"
```

Only restore production after the restore test succeeds and the service owner approves the downtime window.

## Private Document Storage

Document files live in S3-compatible private document storage. Use the storage provider's versioning, lifecycle, and replication controls when available.

Before a risky migration, snapshot or sync the bucket with a provider-approved command such as:

```bash
aws s3 sync "s3://$DOCUMENT_STORAGE_BUCKET/$DOCUMENT_STORAGE_KEY_PREFIX/" "./storage-backup/" --only-show-errors
```

Record the storage backup bucket, prefix, local sync location, timestamp, and operator with the backup record.

Do not make raw document files public during backup or restore.

## Restore Test Cadence

Run one restore test before launch and after every backup-process change. The restore test must verify database migrations, a sample catalog record, and a private document object reference.
