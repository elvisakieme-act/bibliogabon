"""Remet `Author.normalized_name` sous une seule convention.

Le champ était écrit à la main, et deux conventions coexistaient : les jeux
de test écrivaient « nze aline », le seed et l'API staff écrivaient
`display_name.lower()`, soit « aline nze ». Comme il pilote `Meta.ordering`,
la liste d'auteurs était triée de deux façons selon l'origine de la ligne.

Le modèle le dérive désormais à l'enregistrement ; cette migration aligne
les lignes déjà en base.

Réversible dans le sens strict — l'opération inverse ne fait rien — mais la
convention d'origine n'est pas restaurable, puisqu'elle n'en était pas une.
"""

from django.db import migrations

from catalog.models import normalize_author_name


def backfill(apps, schema_editor):
    Author = apps.get_model("catalog", "Author")
    to_update = []
    for author in Author.objects.all().only("id", "display_name", "normalized_name"):
        expected = normalize_author_name(author.display_name)
        if author.normalized_name != expected:
            author.normalized_name = expected
            to_update.append(author)
    if to_update:
        Author.objects.bulk_update(to_update, ["normalized_name"], batch_size=500)


def noop(apps, schema_editor):
    """Rien à défaire : la convention d'origine n'en était pas une."""


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_documenttype_collection_collectionitem_and_more"),
    ]

    operations = [migrations.RunPython(backfill, noop)]
