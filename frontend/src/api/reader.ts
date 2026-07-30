import { apiRequest } from "@/api/client";
import type { ReaderPage, ReaderSession } from "@/api/types";

export function createReaderSession(documentId: number | string, access?: string | null) {
  return apiRequest<ReaderSession>("/api/v1/reader/sessions/", {
    method: "POST",
    token: access,
    body: { document_id: Number(documentId) }
  });
}

export function getReaderPage(
  sessionKey: string,
  pageNumber: number,
  access?: string | null
) {
  return apiRequest<ReaderPage>(
    `/api/v1/reader/sessions/${sessionKey}/pages/${pageNumber}/`,
    { token: access }
  );
}

export function closeReaderSession(sessionKey: string, access?: string | null) {
  return apiRequest<void>(`/api/v1/reader/sessions/${sessionKey}/`, {
    method: "DELETE",
    token: access
  });
}
