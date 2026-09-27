/**
 * Valeurs d'énumération du catalogue, côté écran.
 *
 * Elles reproduisent `catalog.Document.Category` et `AccessModel`. Le serveur
 * refuse toute valeur hors liste, donc une divergence se voit immédiatement
 * comme un refus sur le champ — pas comme un enregistrement silencieux.
 */
export const CATEGORY_OPTIONS = [
  { value: "voluntary_teacher_deposit", label: "Dépôt volontaire d'enseignant" },
  { value: "institutional_fund", label: "Fonds institutionnel" },
  { value: "student_work", label: "Travail d'étudiant" },
  { value: "open_resource", label: "Ressource ouverte" },
  { value: "commercial_partner_content", label: "Contenu de partenaire commercial" }
] as const;

export const ACCESS_MODEL_OPTIONS = [
  { value: "free", label: "Libre" },
  { value: "subscription", label: "Abonnement" },
  { value: "institution_only", label: "Institution seulement" },
  { value: "sponsored", label: "Parrainé" },
  { value: "restricted", label: "Restreint" },
  { value: "private", label: "Privé" }
] as const;
