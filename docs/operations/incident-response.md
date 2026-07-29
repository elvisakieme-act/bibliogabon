# Incident Response Runbook

## Triage

- Record detection time, reporter, environment, and visible user impact.
- Check `/health/` for application and database status.
- Review recent application logs at `ERROR` and `WARNING` levels.
- Check whether the issue affects reader access, search, payment, ingestion, or admin workflows.

## Containment

- For reader access incidents, suspend risky entitlements or publication records through existing admin workflows.
- For payment incidents, stop retrying the affected payment provider path and preserve transaction records.
- For document exposure concerns, disable the affected document or storage prefix before investigating content.
- For staff workflow issues, restrict admin access to essential operators.

## Investigation

- Use `operations.AuditLog` to trace publication decisions, support resolutions, report generation, and sensitive admin actions.
- Preserve relevant logs, request IDs, timestamps, and object IDs.
- Do not paste secrets, payment metadata, raw document text, or personal reading data into incident notes.

## Recovery

- Apply the smallest verified fix.
- Run targeted tests and `/health/`.
- Confirm impacted users or institutions can complete the affected workflow.
- Record the recovery timestamp and verification evidence.

## Follow-Up

- Create a post-incident note with cause, impact, response timeline, and prevention work.
- Add regression tests for code defects.
- Update this runbook when response steps were missing or inaccurate.
