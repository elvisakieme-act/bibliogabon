/**
 * Valeurs de `catalog.RightsAgreement`, côté écran.
 *
 * Les statuts d'autorisation sont traduits ici mais **jamais proposés** au
 * déposant : ils sont le résultat de la décision d'un modérateur, pas un
 * champ de formulaire. On les affiche, on ne les choisit pas.
 */
export const AGREEMENT_TYPE_OPTIONS = [
  { value: "teacher_voluntary", label: "Publication volontaire d'enseignant" },
  { value: "institutional_archive", label: "Archive ou fonds institutionnel" },
  { value: "student_consent", label: "Consentement d'un travail d'étudiant" },
  { value: "open_license", label: "Licence ouverte" },
  { value: "commercial_distribution", label: "Distribution commerciale" }
] as const;

export const WITHDRAWAL_RULE_OPTIONS = [
  { value: "author_request", label: "Sur demande de l'auteur" },
  { value: "contract_terms", label: "Selon les termes du contrat" },
  { value: "confidentiality_override", label: "Pour motif de confidentialité" },
  { value: "license_invalid", label: "Si la licence devient invalide" },
  { value: "commercial_terms", label: "Selon les termes commerciaux" }
] as const;

const AUTHORIZATION_STATUS_LABELS: Record<string, string> = {
  draft: "Brouillon",
  pending_review: "En attente de revue",
  approved: "Approuvée",
  rejected: "Rejetée",
  revoked: "Révoquée"
};

export function authorizationStatusLabel(status: string): string {
  return AUTHORIZATION_STATUS_LABELS[status] ?? status;
}

export const AUTHOR_ROLE_OPTIONS = [
  { value: "author", label: "Auteur" },
  { value: "coauthor", label: "Co-auteur" },
  { value: "supervisor", label: "Encadrant" },
  { value: "editor", label: "Éditeur" },
  { value: "institutional_contributor", label: "Contributeur institutionnel" }
] as const;
