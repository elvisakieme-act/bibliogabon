"""Réglages qui valent pour toute la suite.

Rien ici ne décrit le produit : ce sont des ajustements d'environnement qui
évitent à la suite de payer, à chaque test, un coût qui n'a rien à voir avec
ce qu'elle vérifie.
"""

import pytest


@pytest.fixture(autouse=True)
def small_page_renders(settings):
    """Rend les pages en petit, sauf demande contraire d'un test.

    Le tuilage IIIF produit 54 objets et coûte ~1,7 s par page à la
    résolution de production — 300 ppp. Multiplié par les dizaines
    d'ingestions de la suite, cela portait celle-ci au-delà de quarante
    minutes : un coût réel pour l'équipe et pour la CI, payé pour vérifier des
    règles d'accès et de journalisation qui ne dépendent pas de la résolution.

    Le réglage est posé sur les `settings`, **pas** sur une variable
    d'environnement : `config/tests/test_env.py` vérifie la valeur par défaut
    en important les réglages dans un sous-processus, et une variable
    d'environnement s'y propagerait, faisant vérifier au test la valeur de la
    suite plutôt que celle du produit.

    Un test qui a besoin de la vraie résolution la réclame lui-même — la
    fixture `settings` le permet, et plusieurs le font déjà.
    """
    settings.DOCUMENT_PAGE_IMAGE_WIDTH = 480
