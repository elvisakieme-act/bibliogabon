import type { DocumentMetadata } from "@/api/types";

/**
 * Ce que l'accès autorise, dit en une phrase.
 *
 * Un badge « institution_only » ne dit rien à un étudiant : il doit lire s'il
 * peut ouvrir ce document maintenant, et sinon ce qu'il lui manque. Les
 * phrases suivent exactement les cas que le serveur distingue — modèle d'accès
 * **et** raison — parce qu'annoncer un droit qu'on n'a pas, ou l'inverse, est
 * la pire chose qu'une bibliothèque puisse faire à un lecteur pressé.
 */
export function documentAccessNote(document: DocumentMetadata): string {
  const { can_read: canRead, reason, access_model: model } = document.access;

  if (canRead && reason === "free") {
    return "Lecture libre : ce document s'ouvre sans compte ni abonnement.";
  }
  if (canRead) {
    if (model === "institution_only") return "Votre établissement vous ouvre ce document.";
    if (model === "sponsored") return "Un accès sponsorisé vous ouvre ce document.";
    if (model === "subscription") return "Votre abonnement vous ouvre ce document.";
    return "Vous avez un droit de lecture actif sur ce document.";
  }
  if (reason === "authentication_required") {
    if (model === "institution_only") {
      return "Réservé aux membres d'un établissement partenaire. Connectez-vous pour que nous vérifiions votre rattachement.";
    }
    if (model === "sponsored") {
      return "Ouvert par une campagne d'accès sponsorisé. Connectez-vous pour vérifier si elle vous couvre.";
    }
    return "Ce document demande un droit de lecture actif. Connectez-vous pour vérifier le vôtre.";
  }
  if (reason === "entitlement_required") {
    if (model === "institution_only") {
      return "Réservé aux membres d'un établissement partenaire. Votre compte n'y est pas encore rattaché.";
    }
    if (model === "sponsored") {
      return "Aucune campagne d'accès sponsorisé ne couvre ce document pour votre compte.";
    }
    return "Ce document demande un abonnement actif, que votre compte n'a pas.";
  }
  return "Ce document n'est pas accessible à la lecture pour le moment.";
}

/**
 * Le régime de droits, nommé pour un lecteur.
 *
 * `category` décrit la provenance — d'où vient le document et sous quel accord
 * il a été déposé. C'est ce qui explique pourquoi deux documents du même
 * domaine n'offrent pas les mêmes libertés.
 */
const CATEGORIES: Record<string, string> = {
  open_resource: "Ressource ouverte",
  voluntary_teacher_deposit: "Dépôt volontaire d'enseignant",
  student_work: "Travail d'étudiant",
  institutional_fund: "Fonds institutionnel",
  partner_publication: "Publication partenaire"
};

export function documentCategoryLabel(category: string): string | null {
  return CATEGORIES[category] ?? null;
}
