import type { DocumentMetadata } from "@/api/types";

/**
 * Dans son propre module : un fichier qui exporte a la fois un composant de
 * route et une fonction casse la granularite du rechargement a chaud.
 *
 * Le parametre est type sur `DocumentMetadata` plutot que deduit du hook de
 * requete : la forme vient du contrat de l'API, pas de la facon dont un ecran
 * la recupere.
 */
export function documentDetailReadLabel(document: DocumentMetadata) {
  if (document.access.can_read) return "Lire maintenant";
  if (document.access.reason === "authentication_required") return "Se connecter pour lire";
  if (document.access.reason === "entitlement_required") return "Acces requis";
  return "Indisponible";
}
