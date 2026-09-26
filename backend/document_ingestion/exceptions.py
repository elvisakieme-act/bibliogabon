"""Erreurs métier de l'ingestion."""

from __future__ import annotations


class VersionAlreadyIngested(Exception):
    """Une version porte déjà du contenu traité pour ce libellé.

    Remplace l'échec opaque que remontait `create_page_records`
    (« Existing page records conflict with requested page_count ») : la
    collision est une décision à prendre par l'appelant, pas une erreur
    technique. L'exception transporte la version en cause pour qu'il puisse
    choisir entre un nouveau libellé et un remplacement explicite.
    """

    def __init__(self, version):
        self.version = version
        self.version_label = version.version_label
        super().__init__(
            f"La version « {version.version_label} » de ce document contient déjà "
            f"{version.page_count or 0} page(s) traitée(s). Utilisez un nouveau "
            f"libellé de version, ou demandez explicitement un remplacement."
        )
