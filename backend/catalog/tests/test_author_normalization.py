from __future__ import annotations

import pytest

from catalog.models import Author, normalize_author_name


@pytest.mark.parametrize(
    ("display_name", "expected"),
    [
        ("Aline NZE", "aline nze"),
        ("Élise MBA", "elise mba"),
        ("  Brice   ONDO ", "brice ondo"),
        ("Université Omar Bongo", "universite omar bongo"),
        ("", ""),
    ],
)
def test_the_sort_form_is_deterministic(display_name, expected):
    assert normalize_author_name(display_name) == expected


@pytest.mark.django_db
def test_the_field_is_derived_and_ignores_what_a_caller_passes():
    """Le champ pilote l'ordre d'affichage. Deux conventions coexistaient
    parce qu'il etait ecrit a la main ; il ne l'est plus."""
    author = Author.objects.create(display_name="Aline NZE", normalized_name="nze aline")

    author.refresh_from_db()
    assert author.normalized_name == "aline nze"


@pytest.mark.django_db
def test_renaming_an_author_refreshes_its_sort_form():
    author = Author.objects.create(display_name="Aline NZE")
    author.display_name = "Aline NZE-MBA"
    author.save()

    author.refresh_from_db()
    assert author.normalized_name == "aline nze-mba"


@pytest.mark.django_db
def test_authors_sort_the_same_way_whatever_created_them():
    """Le tri par defaut ne depend plus de l'origine de la ligne : c'est ce
    que produisaient les deux conventions.

    Il porte sur le nom affiche, donc « Aline NZE » se classe sous A et non
    sous N. C'est coherent, ce n'est pas l'usage academique : trier par nom
    de famille demande de savoir lequel l'est, ce qu'un nom affiche ne dit
    pas — voir B2 du registre de cloture.
    """
    Author.objects.create(display_name="Brice ONDO", normalized_name="ondo brice")
    Author.objects.create(display_name="Aline NZE")
    Author.objects.create(display_name="Élise MBA", normalized_name="mba elise")

    assert [author.display_name for author in Author.objects.all()] == [
        "Aline NZE",
        "Brice ONDO",
        "Élise MBA",
    ]


@pytest.mark.django_db
def test_bulk_create_bypasses_the_derivation_which_is_a_known_limit():
    """`bulk_create` n'appelle pas `save()`. La limite est documentee sur le
    modele plutot que supposee absente : un import en masse doit appeler
    `normalize_author_name` lui-meme.

    Aucun chemin de production ne l'emprunte pour un auteur ; le test existe
    pour que la limite reste visible si cela change.
    """
    Author.objects.bulk_create([Author(display_name="Aline NZE", normalized_name="nze aline")])

    assert Author.objects.get().normalized_name == "nze aline", (
        "si ceci passe au vert, la derivation couvre desormais bulk_create "
        "et la limite documentee sur le modele doit etre retiree"
    )
