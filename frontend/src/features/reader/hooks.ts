import { useMutation, useQuery } from "@tanstack/react-query";

import {
  closeReaderSession,
  createReaderSession,
  getReaderPage
} from "@/api/reader";
import { useAuth } from "@/auth/AuthProvider";

export function useCreateReaderSession() {
  const { tokens } = useAuth();
  return useMutation({
    mutationFn: (documentId: number | string) =>
      createReaderSession(documentId, tokens?.access)
  });
}

export function useReaderPage(sessionKey: string | null, pageNumber: number) {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["reader-page", sessionKey, pageNumber, tokens?.access ?? null],
    queryFn: () => getReaderPage(sessionKey as string, pageNumber, tokens?.access),
    enabled: Boolean(sessionKey)
  });
}

export function useCloseReaderSession() {
  const { tokens } = useAuth();
  return useMutation({
    mutationFn: (sessionKey: string) => closeReaderSession(sessionKey, tokens?.access)
  });
}
