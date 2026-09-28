"""Idempotence du jeu de démonstration.

Il se présente comme rejouable sans risque. Cela doit inclure la réparation
d'un compte à moitié créé : sinon « rejouable » ne veut dire que « ne casse
rien », ce qui est plus faible que ce que la commande promet.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command

from accounts.models import User

PASSWORD = "demo1234"
RECTOR = "recteur.uob@bibliogabon.ga"


@pytest.mark.django_db
def test_the_seed_gives_every_demo_account_a_usable_password():
    call_command("seed_demo", verbosity=0)

    for user in User.objects.filter(email__endswith="bibliogabon.ga"):
        assert user.check_password(PASSWORD), user.email


@pytest.mark.django_db
def test_replaying_the_seed_repairs_an_unusable_password():
    """Trouvé par le parcours manuel de la tranche 4 : le compte recteur
    existait avec un mot de passe inutilisable, et rejouer le seed ne le
    réparait pas — le mot de passe n'était posé qu'à la création."""
    call_command("seed_demo", verbosity=0)
    rector = User.objects.get(email=RECTOR)
    rector.set_unusable_password()
    rector.save(update_fields=["password"])

    call_command("seed_demo", verbosity=0)

    rector.refresh_from_db()
    assert rector.check_password(PASSWORD)


@pytest.mark.django_db
def test_replaying_the_seed_creates_no_duplicate():
    call_command("seed_demo", verbosity=0)
    first = User.objects.count()

    call_command("seed_demo", verbosity=0)

    assert User.objects.count() == first


@pytest.mark.django_db
def test_replaying_the_seed_restores_a_suspended_demo_membership():
    """Trouvé en démonstrant : un parcours qui suspend un membre laissait le
    jeu de données cassé, et rejouer le seed n'y changeait rien parce que
    `get_or_create` ne répare jamais une ligne existante."""
    from accounts import permissions as roles
    from accounts.models import OrganizationMembership

    call_command("seed_demo", verbosity=0)
    rector = User.objects.get(email=RECTOR)
    assert roles.administered_organization_ids(rector)

    membership = OrganizationMembership.objects.get(user=rector)
    membership.status = OrganizationMembership.Status.SUSPENDED
    membership.save(update_fields=["status"])
    assert roles.administered_organization_ids(rector) == []

    call_command("seed_demo", verbosity=0)

    assert roles.administered_organization_ids(rector), (
        "le seed doit ramener le jeu de démonstration dans un état utilisable"
    )
