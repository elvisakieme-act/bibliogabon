"""Réduit `publication_status` aux cinq états du §8.2, plus le rejet (D014).

`AlterField` seul ne suffirait pas : sur un `CharField`, changer les choix ne
touche pas la base, et une ligne portant `rights_review` resterait en place
avec une valeur que le modèle ne reconnaît plus. Elle n'apparaîtrait ni dans
un filtre par état, ni dans un badge — invisible plutôt qu'erronée, ce qui est
pire.

La reprise précède donc l'altération :

- les trois états de revue étaient tous le « en vérification » du plan
  directeur, et redeviennent `submitted` ;
- `suspended` devient `withdrawn`, qui portait déjà le même sens : non
  lisible, traçable, republiable sur nouvelle décision.

Sens inverse impossible : rien ne dit à quelle étape de revue un document
`submitted` se trouvait. L'opération inverse est donc explicitement refusée,
plutôt que silencieusement incomplète.
"""

from django.db import migrations, models

REPLACEMENTS = {
    "rights_review": "submitted",
    "technical_processing": "submitted",
    "editorial_review": "submitted",
    "suspended": "withdrawn",
}


def collapse(apps, schema_editor):
    Document = apps.get_model("catalog", "Document")
    for removed, replacement in REPLACEMENTS.items():
        Document.objects.filter(publication_status=removed).update(
            publication_status=replacement
        )


def irreversible(apps, schema_editor):
    raise migrations.exceptions.IrreversibleError(
        "Rien ne dit a quelle etape de revue un document « submitted » se "
        "trouvait avant la reduction : un retour arriere serait une invention. "
        "Restaurez une sauvegarde anterieure a cette migration."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0005_backfill_normalized_author_names"),
    ]

    operations = [
        migrations.RunPython(collapse, irreversible),
        migrations.AlterField(
            model_name="document",
            name="publication_status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("submitted", "Submitted"),
                    ("published", "Published"),
                    ("withdrawn", "Withdrawn"),
                    ("archived", "Archived"),
                    ("rejected", "Rejected"),
                ],
                default="draft",
                max_length=32,
            ),
        ),
    ]
