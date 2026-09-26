from __future__ import annotations

import pytest
from django.core.management import call_command

from catalog.models import Document
from document_processing.models import DocumentPage, ExtractedText


@pytest.mark.django_db
def test_seed_demo_fabricates_no_pages(capsys):
    """Les fausses pages du jeu de demonstration occupaient la version v1 et
    faisaient echouer toute ingestion reelle sur le meme document."""
    call_command("seed_demo")

    assert Document.objects.exists(), "le jeu de demonstration doit creer des documents"
    assert DocumentPage.objects.count() == 0
    assert ExtractedText.objects.count() == 0


@pytest.mark.django_db
def test_seed_demo_tells_how_to_ingest_real_content(capsys):
    call_command("seed_demo")

    output = capsys.readouterr().out
    assert "ingest_file" in output


@pytest.mark.django_db
def test_seed_demo_is_replayable():
    call_command("seed_demo")
    count = Document.objects.count()

    call_command("seed_demo")

    assert Document.objects.count() == count
