/**
 * Etats de publication, traduits en un seul endroit.
 *
 * Les dix valeurs de `catalog.Document.PublicationStatus`. Un etat ajoute au
 * serveur et absent d'ici s'affiche tel quel, en clair : une ligne sans badge
 * se lirait comme « pas d'etat », et le nouvel etat disparaitrait
 * silencieusement de l'ecran.
 *
 * Dans son propre module, et non dans le composant : un fichier qui exporte
 * a la fois des composants et des valeurs casse la granularite du
 * rechargement a chaud.
 */
export const PUBLICATION_STATUS_LABELS: Record<string, string> = {
  draft: "Brouillon",
  submitted: "Soumis",
  rights_review: "Examen des droits",
  technical_processing: "Traitement technique",
  editorial_review: "Relecture editoriale",
  published: "Publie",
  withdrawn: "Retire",
  archived: "Archive",
  rejected: "Rejete",
  suspended: "Suspendu"
};

export const PUBLICATION_STATUS_TONES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700",
  submitted: "bg-blue-100 text-blue-800",
  rights_review: "bg-amber-100 text-amber-900",
  technical_processing: "bg-amber-100 text-amber-900",
  editorial_review: "bg-amber-100 text-amber-900",
  published: "bg-emerald-100 text-emerald-800",
  withdrawn: "bg-orange-100 text-orange-900",
  archived: "bg-slate-200 text-slate-700",
  rejected: "bg-red-100 text-red-800",
  suspended: "bg-red-100 text-red-800"
};

export function publicationStatusLabel(status: string): string {
  return PUBLICATION_STATUS_LABELS[status] ?? status;
}

export const PUBLICATION_STATUS_OPTIONS = Object.entries(PUBLICATION_STATUS_LABELS).map(
  ([value, label]) => ({ value, label })
);
