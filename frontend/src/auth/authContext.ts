import { createContext } from "react";

import type { ApiUser, AuthTokens } from "@/api/types";

/**
 * Le contexte vit dans son propre module, et non aux cotes du fournisseur :
 * un fichier qui exporte a la fois un composant et une valeur casse la
 * granularite du rechargement a chaud, et editer le fournisseur rechargerait
 * tout l'arbre au lieu de lui seul.
 */
export interface AuthContextValue {
  user: ApiUser | null;
  tokens: AuthTokens | null;
  isHydrating: boolean;
  setSession(session: { user: ApiUser; tokens: AuthTokens }): void;
  clearSession(): void;
  logout(): Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
