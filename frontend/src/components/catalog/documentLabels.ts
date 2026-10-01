import type { DocumentMetadata } from "@/api/types";

export function documentReadLabel(document: DocumentMetadata) {
  if (document.access.can_read) return "Lire";
  if (document.access.reason === "authentication_required") return "Connexion requise";
  if (document.access.reason === "entitlement_required") return "Accès requis";
  return "Indisponible";
}
