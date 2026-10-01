from django.conf import settings


def test_development_keeps_no_persistent_database_connection():
    """
    `runserver` crée un fil par requête et ne le réutilise pas : une connexion
    gardée en réserve reste donc ouverte pour un fil déjà mort.

    En ouvrant un document de 157 pages, dont le lecteur demande les images par
    rafales, les cent connexions de PostgreSQL ont été épuisées en une minute.
    Le symptôme était une erreur 500 sur le *catalogue* — à l'autre bout de
    l'application, et sans rapport visible avec la lecture : exactement le genre
    de piste qui fait chercher le défaut là où il n'est pas.

    La réserve garde tout son sens en production, où un serveur à processus
    fixes réutilise vraiment ses connexions.
    """
    assert settings.DJANGO_ENV == "development"
    assert settings.DATABASES["default"]["CONN_MAX_AGE"] == 0
