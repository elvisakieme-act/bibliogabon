import type { AccountType } from "@/api/types";

/**
 * Miroir de `accounts.permissions.has_back_office_access`.
 *
 * Le serveur reste la seule autorite : cette liste evite d'afficher une
 * porte qui claquera, elle ne protege rien. Chaque ecran de gestion doit
 * donc rendre un refus serveur comme un cas normal, jamais comme un imprevu.
 *
 * Dans son propre module, et non dans `guards.tsx` : un fichier qui exporte
 * a la fois des composants et des valeurs casse la granularite du
 * rechargement a chaud.
 */
export const BACK_OFFICE_ACCOUNT_TYPES: readonly AccountType[] = [
  "teacher_author",
  "organization_admin",
  "content_admin",
  "platform_staff"
];

/**
 * Miroir de `accounts.permissions.is_content_admin`, qui englobe le staff
 * plateforme.
 *
 * Sert à ne pas **afficher** ce que le serveur refusera. Le journal d'audit
 * en est l'exemple : la fiche d'un document le demandait sans condition, et
 * l'écran d'un enseignant enchaînait donc des 403 à chaque rendu. Une requête
 * dont on sait qu'elle échouera n'est pas une vérification, c'est du bruit —
 * dans la console, dans les journaux du serveur, et dans la tête de qui
 * diagnostique.
 *
 * Le serveur reste la seule autorité : ce miroir évite un appel inutile, il
 * n'autorise rien.
 */
export function isContentAdmin(accountType: AccountType | undefined): boolean {
  return accountType === "content_admin" || accountType === "platform_staff";
}
