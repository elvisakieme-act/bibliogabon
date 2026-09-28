import { apiBaseUrl, ApiError } from "@/api/client";

/**
 * Récupère l'image d'une page du lecteur.
 *
 * Une balise `<img src="…">` **ne peut pas** porter d'en-tête
 * d'authentification. Le lecteur affichait donc des pages vides pour tout
 * utilisateur connecté : le serveur refusait chaque image avec un 403, et
 * aucun test ne pouvait le voir — le client de test authentifie la requête,
 * et une vérification en ligne de commande pose l'en-tête à la main.
 *
 * L'image est donc demandée comme les autres ressources, avec le jeton, et
 * remise au navigateur sous forme de `blob:`. L'autorisation reste vérifiée à
 * chaque requête, ce qu'une adresse signée glissée dans l'URL ne ferait plus.
 */
export async function fetchReaderPageImage(path: string, token?: string | null): Promise<Blob> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  if (!response.ok) {
    throw new ApiError(
      response.status,
      "page_image_unavailable",
      "Cette page n'a pas pu être affichée."
    );
  }
  return response.blob();
}
