import { apiRequest } from "@/api/client";
import type {
  DocumentMetadata,
  DomainSummary,
  PaginatedResponse,
  SearchResult
} from "@/api/types";

type QueryValue = string | number | boolean | null | undefined;

function withQuery(path: string, params: Record<string, QueryValue> = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const serialized = query.toString();
  return serialized ? `${path}?${serialized}` : path;
}

export function listDocuments(
  params: Record<string, QueryValue> = {},
  token?: string | null
) {
  return apiRequest<PaginatedResponse<DocumentMetadata>>(
    withQuery("/api/v1/catalog/documents/", params),
    { token }
  );
}

export function getDocument(documentId: number | string, token?: string | null) {
  return apiRequest<DocumentMetadata>(`/api/v1/catalog/documents/${documentId}/`, {
    token
  });
}

export function listDomains(params: Record<string, QueryValue> = {}) {
  return apiRequest<PaginatedResponse<DomainSummary>>(
    withQuery("/api/v1/catalog/domains/", params)
  );
}

export function searchDocuments(
  params: Record<string, QueryValue> = {},
  token?: string | null
) {
  return apiRequest<PaginatedResponse<SearchResult>>(withQuery("/api/v1/search/", params), {
    token
  });
}
