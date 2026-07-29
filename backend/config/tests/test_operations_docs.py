from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("relative_path", "required_phrases"),
    [
        (
            "docs/operations/deployment-checklist.md",
            [
                "python manage.py check",
                "python manage.py migrate",
                "DJANGO_ENV=production",
                "/health/",
                "Rollback",
            ],
        ),
        (
            "docs/operations/backup-and-restore.md",
            [
                "pg_dump",
                "psql",
                "S3-compatible",
                "restore test",
                "private document storage",
            ],
        ),
        (
            "docs/operations/incident-response.md",
            [
                "Triage",
                "Containment",
                "AuditLog",
                "payment",
                "reader access",
            ],
        ),
    ],
)
def test_operations_runbooks_contain_operator_steps(relative_path, required_phrases):
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    for phrase in required_phrases:
        assert phrase in text


def test_agents_guide_matches_current_backend_stack():
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "Django backend" in text
    assert "backend/" in text
    assert "pytest" in text
    assert "python manage.py check" in text
