import { useQuery } from "@tanstack/react-query";

import { getDocument, listDocuments, listDomains, searchDocuments } from "@/api/catalog";
import { useAuth } from "@/auth/AuthProvider";

export function useDocuments(params: Record<string, string | number | undefined>) {
  const { tokens } = useAuth();
  return useQuery({ queryKey: ["documents", params, tokens?.access ?? null], queryFn: () => listDocuments(params, tokens?.access) });
}

export function useDocument(documentId: string | number) {
  const { tokens } = useAuth();
  return useQuery({ queryKey: ["document", documentId, tokens?.access ?? null], queryFn: () => getDocument(documentId, tokens?.access) });
}

export function useDomains() {
  return useQuery({ queryKey: ["domains"], queryFn: () => listDomains() });
}

export function useSearch(params: Record<string, string | number | undefined>) {
  const { tokens } = useAuth();
  return useQuery({ queryKey: ["search", params, tokens?.access ?? null], queryFn: () => searchDocuments(params, tokens?.access) });
}
