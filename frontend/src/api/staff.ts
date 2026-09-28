import { apiRequest } from "@/api/client";
import type {
  PaginatedResponse,
  ReviewDecision,
  RightsDecision,
  RightsDeclaration,
  StaffAuditEvent,
  StaffAuthorProfile,
  StaffDocument,
  StaffIndex,
  StaffDocumentFilters,
  StaffIngestionStatus,
  StaffInstitutionReport,
  StaffMembership,
  StaffOrganization,
  StaffQuota,
  StaffReview,
  StaffReviewFilters,
  StaffTicket,
  StaffTicketFilters
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
 * Ce que le serveur accepte en depot. Les bornes viennent de sa
 * configuration, jamais d'une variable de build : recopiees cote client,
 * elles derivaient de la realite sans que rien ne le signale.
 */
export function getStaffIndex(token: string, signal?: AbortSignal) {
  return apiRequest<StaffIndex>(`${BASE}/`, { token, signal });
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

export function listStaffReviews({
  token,
  filters,
  signal
}: {
  token: string;
  filters?: StaffReviewFilters;
  signal?: AbortSignal;
}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const query = params.toString();
  return apiRequest<PaginatedResponse<StaffReview>>(
    `${BASE}/reviews/${query ? `?${query}` : ""}`,
    { token, signal }
  );
}

export function getStaffReview(reviewId: number, token: string, signal?: AbortSignal) {
  return apiRequest<StaffReview>(`${BASE}/reviews/${reviewId}/`, { token, signal });
}

export function openStaffReview(documentId: number, token: string) {
  return apiRequest<StaffReview>(`${BASE}/reviews/`, {
    method: "POST",
    token,
    body: { document: documentId }
  });
}

export function assignStaffReview(reviewId: number, token: string) {
  return apiRequest<StaffReview>(`${BASE}/reviews/${reviewId}/assign/`, {
    method: "POST",
    token,
    body: {}
  });
}

export function decideStaffReview(reviewId: number, payload: ReviewDecision, token: string) {
  return apiRequest<StaffReview>(`${BASE}/reviews/${reviewId}/decision/`, {
    method: "POST",
    token,
    body: payload
  });
}

export function withdrawStaffDocument(documentId: number, reason: string, token: string) {
  return apiRequest<StaffDocument>(documentPath(documentId, "withdraw/"), {
    method: "POST",
    token,
    body: { reason }
  });
}

export function archiveStaffDocument(documentId: number, reason: string, token: string) {
  return apiRequest<StaffDocument>(documentPath(documentId, "archive/"), {
    method: "POST",
    token,
    body: { reason }
  });
}

export function getDocumentAudit(documentId: number, token: string, signal?: AbortSignal) {
  return apiRequest<PaginatedResponse<StaffAuditEvent>>(documentPath(documentId, "audit/"), {
    token,
    signal
  });
}

// --- Organisations ----------------------------------------------------------

function organizationPath(organizationId: number, suffix = "") {
  return `${BASE}/organizations/${organizationId}/${suffix}`;
}

export function listStaffOrganizations(token: string, signal?: AbortSignal) {
  return apiRequest<PaginatedResponse<StaffOrganization>>(`${BASE}/organizations/`, {
    token,
    signal
  });
}

export function getStaffOrganization(
  organizationId: number,
  token: string,
  signal?: AbortSignal
) {
  return apiRequest<StaffOrganization>(organizationPath(organizationId), { token, signal });
}

export function listOrganizationMembers(
  organizationId: number,
  token: string,
  signal?: AbortSignal
) {
  return apiRequest<PaginatedResponse<StaffMembership>>(
    organizationPath(organizationId, "members/"),
    { token, signal }
  );
}

export function addOrganizationMember(
  organizationId: number,
  payload: { email: string; role: string },
  token: string
) {
  return apiRequest<StaffMembership>(organizationPath(organizationId, "members/"), {
    method: "POST",
    token,
    body: payload
  });
}

export function suspendOrganizationMember(
  organizationId: number,
  membershipId: number,
  reason: string,
  token: string
) {
  return apiRequest<StaffMembership>(
    organizationPath(organizationId, `members/${membershipId}/suspend/`),
    { method: "POST", token, body: { reason } }
  );
}

export function endOrganizationMember(
  organizationId: number,
  membershipId: number,
  reason: string,
  token: string
) {
  return apiRequest<StaffMembership>(
    organizationPath(organizationId, `members/${membershipId}/end/`),
    { method: "POST", token, body: { reason } }
  );
}

export function listOrganizationQuotas(
  organizationId: number,
  token: string,
  signal?: AbortSignal
) {
  return apiRequest<PaginatedResponse<StaffQuota>>(
    organizationPath(organizationId, "quotas/"),
    { token, signal }
  );
}

export function getOrganizationReport(
  organizationId: number,
  period: { from?: string; to?: string },
  token: string,
  signal?: AbortSignal
) {
  const params = new URLSearchParams();
  if (period.from) params.set("from", period.from);
  if (period.to) params.set("to", period.to);
  const query = params.toString();
  return apiRequest<StaffInstitutionReport>(
    `${organizationPath(organizationId, "report/")}${query ? `?${query}` : ""}`,
    { token, signal }
  );
}

// --- Support, signalements et demandes de retrait ---------------------------

export function listStaffTickets({
  token,
  filters,
  signal
}: {
  token: string;
  filters?: StaffTicketFilters;
  signal?: AbortSignal;
}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const query = params.toString();
  return apiRequest<PaginatedResponse<StaffTicket>>(
    `${BASE}/tickets/${query ? `?${query}` : ""}`,
    { token, signal }
  );
}

export function assignStaffTicket(ticketId: number, token: string) {
  return apiRequest<StaffTicket>(`${BASE}/tickets/${ticketId}/assign/`, {
    method: "POST",
    token,
    body: {}
  });
}

export function resolveStaffTicket(ticketId: number, resolutionSummary: string, token: string) {
  return apiRequest<StaffTicket>(`${BASE}/tickets/${ticketId}/resolve/`, {
    method: "POST",
    token,
    body: { resolution_summary: resolutionSummary }
  });
}

export function getDocumentIngestion(documentId: number, token: string, signal?: AbortSignal) {
  return apiRequest<StaffIngestionStatus>(documentPath(documentId, "ingestion/"), {
    token,
    signal
  });
}
