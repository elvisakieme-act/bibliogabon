/**
 * États d'adhésion et de vérification, traduits en un seul endroit.
 *
 * `verification_status` mérite une attention particulière : une adhésion non
 * vérifiée **n'accorde aucun accès**, et l'écran doit le dire plutôt que de
 * laisser un administrateur conclure que la plateforme est cassée quand un
 * membre actif ne peut pas lire.
 */
export const MEMBERSHIP_STATUS_LABELS: Record<string, string> = {
  active: "Active",
  suspended: "Suspendue",
  ended: "Terminée",
  invited: "Invitée"
};

export const VERIFICATION_STATUS_LABELS: Record<string, string> = {
  unverified: "Non vérifiée",
  pending: "Vérification en cours",
  verified: "Vérifiée",
  rejected: "Vérification rejetée"
};

export const MEMBERSHIP_ROLE_LABELS: Record<string, string> = {
  member: "Membre",
  admin: "Administrateur",
  librarian: "Bibliothécaire",
  teacher: "Enseignant"
};

export function membershipStatusLabel(status: string): string {
  return MEMBERSHIP_STATUS_LABELS[status] ?? status;
}

export function verificationStatusLabel(status: string): string {
  return VERIFICATION_STATUS_LABELS[status] ?? status;
}

export function membershipRoleLabel(role: string): string {
  return MEMBERSHIP_ROLE_LABELS[role] ?? role;
}

/** Une adhésion n'ouvre l'accès que si elle est active **et** vérifiée. */
export function grantsAccess(status: string, verificationStatus: string): boolean {
  return status === "active" && verificationStatus === "verified";
}
