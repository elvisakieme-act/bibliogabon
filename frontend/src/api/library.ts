import { apiRequest } from "@/api/client";
import type {
  FavoriteItem,
  PaginatedResponse,
  ReadingProgressItem
} from "@/api/types";

function pagePath(path: string, page: number) {
  return `${path}?${new URLSearchParams({ page: String(page) }).toString()}`;
}

export function listFavorites(access: string, page = 1) {
  return apiRequest<PaginatedResponse<FavoriteItem>>(pagePath(
    "/api/v1/me/favorites/",
    page
  ), {
    token: access
  });
}

export function addFavorite(access: string, documentId: number | string) {
  return apiRequest<FavoriteItem>("/api/v1/me/favorites/", {
    method: "POST",
    token: access,
    body: { document_id: Number(documentId) }
  });
}

export function removeFavorite(access: string, documentId: number | string) {
  return apiRequest<void>(`/api/v1/me/favorites/${documentId}/`, {
    method: "DELETE",
    token: access
  });
}

export function listReadingProgress(access: string, page = 1) {
  return apiRequest<PaginatedResponse<ReadingProgressItem>>(
    pagePath("/api/v1/me/reading-progress/", page),
    { token: access }
  );
}

export function updateReadingProgress(
  access: string,
  documentId: number | string,
  lastPageNumber: number
) {
  return apiRequest<ReadingProgressItem>(
    `/api/v1/me/reading-progress/${documentId}/`,
    {
      method: "PATCH",
      token: access,
      body: { last_page_number: lastPageNumber }
    }
  );
}
