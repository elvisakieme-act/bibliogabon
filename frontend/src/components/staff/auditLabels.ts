/**
 * Types d'événement d'audit, traduits en un seul endroit.
 *
 * Un type inconnu de l'interface s'affiche **tel quel**, jamais masqué : le
 * journal est la preuve visible d'une garantie de traçabilité, et une ligne
 * escamotée parce que l'écran ne la connaît pas trahit cette garantie plus
 * sûrement qu'un libellé technique.
 *
 * Cette table n'est pas couverte par le garde-fou de parité des énumérations :
 * `event_type` est une chaîne libre côté serveur, pas un `TextChoices`. C'est
 * précisément pourquoi la dégradation doit être visible.
 */
const LABELS: Record<string, string> = {
  document_created: "Création du document",
  document_updated: "Modification des métadonnées",
  document_submitted: "Soumission à la revue",
  document_source_uploaded: "Dépôt du fichier source",
  document_withdrawn: "Retrait du public",
  document_archived: "Archivage",
  publication_review_opened: "Ouverture de la revue",
  publication_review_approved: "Approbation et publication",
  publication_review_rejected: "Rejet",
  publication_review_cancelled: "Annulation de la revue",
  rights_agreement_approved: "Approbation des droits",
  rights_agreement_rejected: "Rejet des droits",
  document_author_attached: "Rattachement d'un auteur",
  document_author_detached: "Détachement d'un auteur"
};

export function auditEventLabel(eventType: string): string {
  return LABELS[eventType] ?? eventType;
}

export function isKnownAuditEvent(eventType: string): boolean {
  return eventType in LABELS;
}
