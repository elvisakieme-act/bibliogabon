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
