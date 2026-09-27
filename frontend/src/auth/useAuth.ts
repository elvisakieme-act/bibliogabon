import { useContext } from "react";

import { AuthContext } from "@/auth/authContext";

/**
 * Dans son propre module, et non aux cotes du fournisseur : un fichier qui
 * exporte a la fois un composant et une valeur casse la granularite du
 * rechargement a chaud, et editer le hook rechargerait tout l'arbre.
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
