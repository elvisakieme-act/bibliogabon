"""Prédicats de rôle : source de vérité unique des permissions.

Trois axes, délibérément distincts :

- l'**identité** dit qui authentifie ;
- le **rôle** dit quelles actions sont permises — c'est ce module ;
- l'**entitlement** dit quel contenu est lisible — c'est `Entitlement`.

Un rôle n'ouvre jamais l'accès à un document, et un entitlement n'autorise
jamais une action de gestion. Les fonctions ci-dessous sont de simples
lectures, sans HTTP ni DRF, pour que l'API, les services et l'admin posent
la même question et obtiennent la même réponse.

La portée organisationnelle est un **argument** du prédicat, jamais un
filtre appliqué après coup : demander « cet utilisateur peut-il gérer des
membres ? » sans dire de quelle organisation n'a pas de sens.
"""

from __future__ import annotations

from accounts.models import Organization, OrganizationMembership, User
from accounts.services import active_organization_ids_for_user


def _is_authenticated(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False))


def _account_type(user) -> str:
    return getattr(user, "account_type", "") if _is_authenticated(user) else ""


# --- Staff plateforme --------------------------------------------------------


def is_platform_staff(user) -> bool:
    """Super administrateur : configuration, facturation, opérations sensibles.

    `is_superuser` compte aussi. Les surcharges `has_*_permission` d'un
    ModelAdmin court-circuitent le bypass superuser de Django : un compte
    racine dont le `account_type` aurait dérivé se retrouverait enfermé
    dehors, sans recours par l'interface. Le filet est délibéré.
    """
    if not _is_authenticated(user):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return _account_type(user) == User.AccountType.PLATFORM_STAFF


def is_content_admin(user) -> bool:
    """Modérateur de contenu, ou super administrateur qui l'englobe."""
    return _account_type(user) == User.AccountType.CONTENT_ADMIN or is_platform_staff(user)


def can_manage_billing(user) -> bool:
    """Réservé au super administrateur : un modérateur de contenu n'a pas
    d'autorité sur les offres, abonnements et paiements."""
    return is_platform_staff(user)


# --- Portée organisationnelle ------------------------------------------------


def administered_organization_ids(user) -> list[int]:
    """Organisations que cet utilisateur administre effectivement.

    S'appuie sur `active_organization_ids_for_user`, donc une adhésion
    suspendue, terminée, ou dont l'identité n'est pas vérifiée quand
    l'organisation l'exige, retire l'autorité administrative exactement
    comme elle retire l'accès en lecture.
    """
    if not _is_authenticated(user):
        return []
    active_ids = active_organization_ids_for_user(user)
    if not active_ids:
        return []
    return list(
        OrganizationMembership.objects.filter(
            user=user,
            organization_id__in=active_ids,
            role=OrganizationMembership.Role.ADMIN,
        ).values_list("organization_id", flat=True)
    )


def administers_organization(user, organization: Organization) -> bool:
    if is_platform_staff(user):
        return True
    if organization is None:
        return False
    return organization.pk in administered_organization_ids(user)


def can_manage_organization_members(user, organization: Organization) -> bool:
    """Inviter, approuver, suspendre, retirer — sur sa propre organisation."""
    return administers_organization(user, organization)


def can_view_organization_reports(user, organization: Organization) -> bool:
    """Rapports agrégés de son organisation. Jamais un historique de lecture
    personnel : c'est `analytics` qui garantit l'agrégation."""
    return administers_organization(user, organization)


# --- Documents ---------------------------------------------------------------


def can_submit_document(user) -> bool:
    """Déposer une ressource. Ouvert à l'enseignant-auteur ; un modérateur de
    contenu peut déposer pour le compte d'un tiers."""
    return _account_type(user) == User.AccountType.TEACHER_AUTHOR or is_content_admin(user)


def can_review_publication(user) -> bool:
    """Valider métadonnées, droits, statut et publication."""
    return is_content_admin(user)


# Catégories dont le retrait suit un contrat, pas la volonté de l'auteur.
# Valeurs littérales à dessein : `catalog` dépend de `accounts`, donc ce
# module ne peut pas importer `Document` sans inverser la dépendance. Un
# test verrouille la correspondance avec `Document.Category`.
CONTRACT_BOUND_CATEGORIES = frozenset(
    {
        "institutional_fund",
        "commercial_partner_content",
    }
)


def _user_authored(user, document) -> bool:
    if not _is_authenticated(user):
        return False
    return document.document_authors.filter(author__linked_user=user).exists()


def can_withdraw_document(user, document) -> bool:
    """Retrait d'un document.

    « Les enseignants-auteurs peuvent demander le retrait de leurs dépôts
    volontaires, mais les fonds institutionnels suivent les règles du
    contrat. » Un administrateur d'institution ne retire rien globalement.
    """
    if is_content_admin(user):
        return True
    if document is None:
        return False
    if document.category in CONTRACT_BOUND_CATEGORIES:
        return False
    return _user_authored(user, document)
