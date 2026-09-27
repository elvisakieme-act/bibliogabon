import { ApiError, UNAUTHORIZED_EVENT, apiBaseUrl } from "@/api/client";
import type { ApiErrorEnvelope } from "@/api/types";

/**
 * Envoi de fichier, seul endroit du projet à utiliser `XMLHttpRequest`.
 *
 * `fetch` ne sait pas observer la progression d'un *envoi* dans un
 * navigateur : `ReadableStream` en corps de requête n'est pas disponible
 * partout, et même là où il l'est, il ne donne pas d'octets écrits. Or le
 * dépôt est le seul moment du produit où un utilisateur attend devant un
 * transfert qui peut durer : une barre muette y est un défaut, pas un
 * détail. `XMLHttpRequest` reste la seule API qui expose `upload.progress`.
 *
 * Tout le reste — enveloppe d'erreur, jeton, événement de session perdue —
 * est aligné sur `apiRequest`, pour qu'un appelant n'ait pas deux
 * comportements à connaître.
 */
export interface ApiUploadOptions {
  token?: string | null;
  replace?: boolean;
  onProgress?: (ratio: number) => void;
  signal?: AbortSignal;
}

function parseUploadError(status: number, responseText: string): ApiError {
  try {
    const payload = JSON.parse(responseText) as ApiErrorEnvelope;
    if (payload.error) {
      return new ApiError(
        status,
        payload.error.code,
        payload.error.message,
        payload.error.field_errors
      );
    }
  } catch {
    // Un proxy ou un pare-feu peut répondre du HTML. Sans ce garde-fou, la
    // réponse deviendrait un succès muet et l'écran afficherait « déposé ».
    return new ApiError(status, "invalid_response", "La réponse du serveur est illisible.");
  }
  return new ApiError(status, "request_failed", "L'envoi du fichier a échoué.");
}

export function apiUpload<T>(
  path: string,
  file: File,
  options: ApiUploadOptions = {}
): Promise<T> {
  const url = new URL(path.startsWith("http") ? path : `${apiBaseUrl()}${path}`);
  if (options.replace) {
    url.searchParams.set("replace", "true");
  }

  return new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    const body = new FormData();
    body.append("file", file);

    request.open("POST", url.toString());
    request.setRequestHeader("Accept", "application/json");
    if (options.token) {
      request.setRequestHeader("Authorization", `Bearer ${options.token}`);
    }
    // Pas de Content-Type : le navigateur doit écrire lui-même la frontière
    // multipart. La fixer à la main produit un corps que le serveur ne sait
    // pas découper, et l'erreur ressemble à « aucun fichier reçu ».

    if (options.onProgress) {
      request.upload.addEventListener("progress", (event: ProgressEvent) => {
        if (event.lengthComputable && event.total > 0) {
          options.onProgress?.(event.loaded / event.total);
        }
      });
    }

    const abort = () => request.abort();
    options.signal?.addEventListener("abort", abort, { once: true });

    const settled = () => options.signal?.removeEventListener("abort", abort);

    request.addEventListener("load", () => {
      settled();
      if (request.status >= 200 && request.status < 300) {
        if (request.status === 204 || !request.responseText) {
          resolve(undefined as T);
          return;
        }
        try {
          resolve(JSON.parse(request.responseText) as T);
        } catch {
          reject(
            new ApiError(
              request.status,
              "invalid_response",
              "La réponse du serveur est illisible."
            )
          );
        }
        return;
      }
      const error = parseUploadError(request.status, request.responseText);
      if (error.status === 401 && options.token) {
        window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
      }
      reject(error);
    });

    request.addEventListener("error", () => {
      settled();
      reject(new ApiError(0, "network_error", "Le fichier n'a pas pu être transmis."));
    });

    request.addEventListener("abort", () => {
      settled();
      const error = new Error("Envoi annulé.");
      error.name = "AbortError";
      reject(error);
    });

    request.send(body);
  });
}
