/**
 * Catégories, états et priorités de ticket, traduits en un seul endroit.
 *
 * Une catégorie inconnue de l'interface s'affiche telle quelle. Le garde-fou
 * de parité côté backend couvre `SupportTicket.Category`, donc une valeur
 * ajoutée au serveur fait échouer la CI — mais l'affichage brut reste le
 * comportement correct entre-temps : une ligne sans catégorie se lirait comme
 * une demande de support ordinaire, et une demande de retrait y passerait
 * inaperçue.
 */
const CATEGORY_LABELS: Record<string, string> = {
  support: "Demande de support",
  document_report: "Signalement de document",
  withdrawal_request: "Demande de retrait"
};

const STATUS_LABELS: Record<string, string> = {
  open: "Ouverte",
  in_progress: "En cours",
  waiting: "En attente",
  resolved: "Résolue",
  cancelled: "Annulée"
};

const PRIORITY_LABELS: Record<string, string> = {
  low: "Basse",
  normal: "Normale",
  high: "Haute",
  urgent: "Urgente"
};

export const TICKET_CATEGORY_OPTIONS = Object.entries(CATEGORY_LABELS).map(
  ([value, label]) => ({
    value,
    label
  })
);

export const TICKET_STATUS_OPTIONS = Object.entries(STATUS_LABELS).map(([value, label]) => ({
  value,
  label
}));

export function ticketCategoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

export function isKnownTicketCategory(category: string): boolean {
  return category in CATEGORY_LABELS;
}

export function ticketStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function ticketPriorityLabel(priority: string): string {
  return PRIORITY_LABELS[priority] ?? priority;
}
