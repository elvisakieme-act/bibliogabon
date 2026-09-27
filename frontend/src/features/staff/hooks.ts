import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addDocumentAuthor,
  createStaffDocument,
  decideDocumentRights,
  declareDocumentRights,
  getDocumentIngestion,
  getStaffIndex,
  getStaffDocument,
  listStaffDocuments,
  removeDocumentAuthor,
  searchStaffAuthors,
  submitStaffDocument,
  updateStaffDocument
} from "@/api/staff";
import type { RightsDecision, RightsDeclaration, StaffDocumentFilters } from "@/api/types";
import { useAuth } from "@/auth/AuthProvider";

/**
 * Le jeton entre dans la cle de cache : deux comptes n'ont pas le meme
 * perimetre — un enseignant ne voit que ses depots — et servir a l'un les
 * lignes mises en cache pour l'autre serait une fuite, pas un detail de
 * performance.
 */
function useStaffToken() {
  const { tokens } = useAuth();
  return tokens?.access ?? null;
}

export function useStaffDocuments(filters: StaffDocumentFilters) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "documents", filters, token],
    queryFn: ({ signal }) => listStaffDocuments({ token: token as string, filters, signal }),
    enabled: Boolean(token)
  });
}

export function useStaffIndex() {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "index", token],
    queryFn: ({ signal }) => getStaffIndex(token as string, signal),
    enabled: Boolean(token),
    // La configuration de depot ne change pas en cours de session.
    staleTime: Infinity
  });
}

export function useStaffAuthors(q: string) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "authors", q, token],
    queryFn: ({ signal }) => searchStaffAuthors({ token: token as string, q, signal }),
    enabled: Boolean(token)
  });
}

export function useStaffDocument(documentId: number) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "document", documentId, token],
    queryFn: ({ signal }) => getStaffDocument(documentId, token as string, signal),
    enabled: Boolean(token) && Number.isFinite(documentId)
  });
}

/**
 * Le suivi d'ingestion est interroge tant que le travail court, et cesse des
 * qu'il aboutit ou echoue. C'est le seul endroit du produit ou un
 * utilisateur attend un worker : l'attente doit etre lisible, pas un
 * tourniquet sans fin.
 */
export function useDocumentIngestion(documentId: number, { poll = true } = {}) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "ingestion", documentId, token],
    queryFn: ({ signal }) => getDocumentIngestion(documentId, token as string, signal),
    enabled: Boolean(token) && Number.isFinite(documentId),
    refetchInterval: (query) =>
      poll && query.state.data?.state === "in_progress" ? 2000 : false
  });
}

function useStaffMutation<TVariables, TResult>(
  run: (variables: TVariables, token: string) => Promise<TResult>,
  { documentId }: { documentId?: number } = {}
) {
  const token = useStaffToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (variables: TVariables) => run(variables, token as string),
    onSuccess: () => {
      // La liste et le document concerne sont invalides ensemble : un etat
      // qui change en detail doit se voir dans la liste au retour.
      queryClient.invalidateQueries({ queryKey: ["staff", "documents"] });
      if (documentId !== undefined) {
        queryClient.invalidateQueries({ queryKey: ["staff", "document", documentId] });
      }
    }
  });
}

export function useCreateStaffDocument() {
  return useStaffMutation((payload: object, token) => createStaffDocument(payload, token));
}

export function useUpdateStaffDocument(documentId: number) {
  return useStaffMutation(
    (payload: object, token) => updateStaffDocument(documentId, payload, token),
    { documentId }
  );
}

export function useSubmitStaffDocument(documentId: number) {
  return useStaffMutation((_: void, token) => submitStaffDocument(documentId, token), {
    documentId
  });
}

export function useAddDocumentAuthor(documentId: number) {
  return useStaffMutation(
    (payload: { author: number; role: string }, token) =>
      addDocumentAuthor(documentId, payload, token),
    { documentId }
  );
}

export function useRemoveDocumentAuthor(documentId: number) {
  return useStaffMutation(
    (authorId: number, token) => removeDocumentAuthor(documentId, authorId, token),
    { documentId }
  );
}

export function useDeclareDocumentRights(documentId: number) {
  return useStaffMutation(
    (payload: RightsDeclaration, token) => declareDocumentRights(documentId, payload, token),
    { documentId }
  );
}

export function useDecideDocumentRights(documentId: number) {
  return useStaffMutation(
    (payload: RightsDecision, token) => decideDocumentRights(documentId, payload, token),
    { documentId }
  );
}
