"""Ingère un PDF local dans un document existant (pipeline synchrone, dev).

    python manage.py ingest_file <document_id> /chemin/vers/fichier.pdf
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Ingère un fichier PDF local dans un document (pipeline synchrone, développement)."

    def add_arguments(self, parser):
        parser.add_argument("document_id", type=int, help="Identifiant du document cible.")
        parser.add_argument("pdf_path", type=str, help="Chemin du fichier PDF à ingérer.")
        parser.add_argument("--version-label", default="v1", help="Libellé de version (défaut : v1).")

    def handle(self, *args, **options):
        from catalog.models import Document
        from document_ingestion.pipeline import ingest_document_file

        path = Path(options["pdf_path"])
        if not path.is_file():
            raise CommandError(f"Fichier introuvable : {path}")

        try:
            document = Document.objects.get(pk=options["document_id"])
        except Document.DoesNotExist as exc:
            raise CommandError(f"Aucun document avec l'id {options['document_id']}.") from exc

        with path.open("rb") as handle:
            version = ingest_document_file(
                document=document,
                fileobj=handle,
                original_filename=path.name,
                uploaded_by=None,
                version_label=options["version_label"],
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Ingéré : « {document.title} » → version {version.version_label}, "
                f"{version.page_count} page(s), statut {version.status}."
            )
        )
        self.stdout.write("Le document est maintenant lisible via le lecteur et interrogeable par la recherche.")