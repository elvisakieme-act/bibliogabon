/**
 * Codes de complétude, traduits en un seul endroit.
 *
 * Les douze codes stables de `catalog.services`. Un code ajouté au serveur
 * et absent d'ici s'affiche **tel quel**, jamais omis : une liste qui
 * l'omettrait dirait au déposant qu'il ne manque rien, alors que la
 * soumission sera refusée. Un code brut à l'écran est laid ; une soumission
 * refusée sans raison visible est un défaut.
 */
const LABELS: Record<string, string> = {
  title: "Un titre",
  academic_domain: "Un domaine académique",
  document_type: "Un type de document",
  category: "Une catégorie de contenu valide",
  access_model: "Un modèle d'accès valide",
  author: "Au moins un auteur ou co-auteur",
  rights_agreement: "Une déclaration de droits",
  rights_holder: "Le nom du titulaire des droits",
  withdrawal_rule: "Une règle de retrait",
  rights_access_model_mismatch:
    "Le modèle d'accès déclaré doit correspondre à celui du document",
  student_consent_reference: "La référence du consentement de l'étudiant",
  rights_agreement_not_approved: "L'approbation de la déclaration par un modérateur"
};

export function completenessLabel(code: string): string {
  return LABELS[code] ?? code;
}

export function isKnownCompletenessCode(code: string): boolean {
  return code in LABELS;
}
