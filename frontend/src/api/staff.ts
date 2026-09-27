import { apiRequest } from "@/api/client";
import type {
  PaginatedResponse,
  RightsDecision,
  RightsDeclaration,
  StaffAuthorProfile,
  StaffDocument,
  StaffDocumentFilters,
  StaffIngestionStatus
} from "@/api/types";

/**
 * Appels typés contre `/api/staff/v1/`.
 *
 * Même hôte, même enveloppe d'erreur, même jeton que l'API publique : tout
 * passe donc par `apiRequest`. Un second client dupliquerait le décodage de
 * l'enveloppe et la plomberie du jeton, et les deux finiraient par
 * divergerpour de mauvaises raisons.
 *
 * Seul l'envoi de fichier fait exception, dans `upload.ts`, et pour une
 * raison technique précise expliquée là-bas.
 */
const BASE = "/api/staff/v1";

function documentPath(documentId: number, suffix = "") {
  return `${BASE}/documents/${documentId}/${suffix}`;
}

export function staffDocumentsQueryString(filters: StaffDocumentFilters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    // Un paramètre vide n'est pas « pas de filtre » : `?q=` ferait filtrer
    // le serveur sur une chaîne vide.
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function listStaffDocuments({
  token,
  filters,
  signal
}: {
  token: string;
  filters?: StaffDocumentFilters;
  signal?: AbortSignal;
}) {
  return apiRequest<PaginatedResponse<StaffDocument>>(
    `${BASE}/documents/${staffDocumentsQueryString(filters)}`,
    { token, signal }
  );
}

/**
 * Registre des auteurs, vu depuis le back-office.
 *
 * L'endpoint public ne liste que les auteurs de documents publies : au
 * moment du depot, c'est exactement le cas qui manque.
 */
export function searchStaffAuthors({
  token,
  q,
  signal
}: {
  token: string;
  q?: string;
  signal?: AbortSignal;
}) {
  return apiRequest<PaginatedResponse<StaffAuthorProfile>>(
    `${BASE}/authors/${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    { token, signal }
  );
}

export function getStaffDocument(documentId: number, token: string, signal?: AbortSignal) {
  return apiRequest<StaffDocument>(documentPath(documentId), { token, signal });
}

export function createStaffDocument(payload: Partial<StaffDocument> | object, token: string) {
  return apiRequest<StaffDocument>(`${BASE}/documents/`, {
    method: "POST",
    token,
    body: payload
  });
}

export function updateStaffDocument(
  documentId: number,
  payload: Partial<StaffDocument> | object,
  token: string
) {
  return apiRequest<StaffDocument>(documentPath(documentId), {
    method: "PATCH",
    token,
    body: payload
  });
}

export function submitStaffDocument(documentId: number, token: string) {
  return apiRequest<StaffDocument>(documentPath(documentId, "submit/"), {
    method: "POST",
    token,
    body: {}
  });
}

export function addDocumentAuthor(
  documentId: number,
  payload: { author: number; role: string },
  token: string
) {
  return apiRequest<StaffDocument>(documentPath(documentId, "authors/"), {
    method: "POST",
    token,
    body: payload
  });
}

/** Repond 204 sans corps : l'ecran doit recharger le document lui-meme. */
export function removeDocumentAuthor(documentId: number, authorId: number, token: string) {
  return apiRequest<void>(documentPath(documentId, `authors/${authorId}/`), {
    method: "DELETE",
    token
  });
}

export function declareDocumentRights(
  documentId: number,
  payload: RightsDeclaration,
  token: string
) {
  return apiRequest<StaffDocument>(documentPath(documentId, "rights/"), {
    method: "PUT",
    token,
    body: payload
  });
}

/**
 * Réservé à la modération. Le client ne le cache pas — le serveur refuse —
 * mais il est séparé de la déclaration pour que la lecture du code montre la
 * séparation des pouvoirs : le déposant déclare, le modérateur décide.
 */
export function decideDocumentRights(
  documentId: number,
  payload: RightsDecision,
  token: string
) {
  return apiRequest<StaffDocument>(documentPath(documentId, "rights/decision/"), {
    method: "POST",
    token,
    body: payload
  });
}

export function getDocumentIngestion(documentId: number, token: string, signal?: AbortSignal) {
  return apiRequest<StaffIngestionStatus>(documentPath(documentId, "ingestion/"), {
    token,
    signal
  });
}
