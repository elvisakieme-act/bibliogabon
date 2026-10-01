import { useQuery } from "@tanstack/react-query";

import {
  getDocument,
  listDocuments,
  listDomains,
  listTypes,
  searchDocuments
} from "@/api/catalog";
import { useAuth } from "@/auth/useAuth";

export function useDocuments(params: Record<string, string | number | undefined>) {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["documents", params, tokens?.access ?? null],
    queryFn: () => listDocuments(params, tokens?.access)
  });
}

export function useDocument(documentId: string | number) {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["document", documentId, tokens?.access ?? null],
    queryFn: () => getDocument(documentId, tokens?.access)
  });
}

export function useDomains() {
  return useQuery({ queryKey: ["domains"], queryFn: () => listDomains() });
}

export function useDocumentTypes() {
  return useQuery({ queryKey: ["document-types"], queryFn: () => listTypes() });
}

export function useSearch(
  params: Record<string, string | number | undefined>,
  options: { enabled?: boolean } = {}
) {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["search", params, tokens?.access ?? null],
    queryFn: () => searchDocuments(params, tokens?.access),
    // Une recherche sans critère renvoie tout le catalogue : quand le critère
    // n'est pas encore connu — le domaine d'un document qui charge — mieux vaut
    // ne pas partir que ramener n'importe quoi.
    enabled: options.enabled ?? true
  });
}
