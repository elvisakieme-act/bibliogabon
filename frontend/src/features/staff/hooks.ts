import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addDocumentAuthor,
  addOrganizationMember,
  archiveStaffDocument,
  assignStaffReview,
  assignStaffTicket,
  createStaffDocument,
  decideDocumentRights,
  decideStaffReview,
  endOrganizationMember,
  declareDocumentRights,
  getDocumentAudit,
  getDocumentIngestion,
  getStaffIndex,
  getOrganizationReport,
  getStaffOrganization,
  getStaffReview,
  listOrganizationMembers,
  listOrganizationQuotas,
  listStaffOrganizations,
  listStaffReviews,
  listStaffTickets,
  openStaffReview,
  resolveStaffTicket,
  getStaffDocument,
  listStaffDocuments,
  removeDocumentAuthor,
  searchStaffAuthors,
  submitStaffDocument,
  suspendOrganizationMember,
  updateStaffDocument,
  withdrawStaffDocument
} from "@/api/staff";
import type {
  ReviewDecision,
  RightsDecision,
  RightsDeclaration,
  StaffDocumentFilters,
  StaffReviewFilters,
  StaffTicketFilters
} from "@/api/types";
import { useAuth } from "@/auth/useAuth";

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
 * qu'il aboutit ou échoue. C'est le seul endroit du produit où un
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

// --- Revue de publication ---------------------------------------------------

export function useStaffReviews(filters: StaffReviewFilters) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "reviews", filters, token],
    queryFn: ({ signal }) => listStaffReviews({ token: token as string, filters, signal }),
    enabled: Boolean(token)
  });
}

export function useStaffReview(reviewId: number) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "review", reviewId, token],
    queryFn: ({ signal }) => getStaffReview(reviewId, token as string, signal),
    enabled: Boolean(token) && Number.isFinite(reviewId)
  });
}

export function useDocumentAudit(documentId: number) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "audit", documentId, token],
    queryFn: ({ signal }) => getDocumentAudit(documentId, token as string, signal),
    enabled: Boolean(token) && Number.isFinite(documentId)
  });
}

/**
 * Les mutations de revue invalident aussi la file : une decision prise sur un
 * dossier doit le faire disparaitre de la liste au retour, sinon un relecteur
 * rouvre ce qu'il vient de traiter.
 */
function useReviewMutation<TVariables, TResult>(
  run: (variables: TVariables, token: string) => Promise<TResult>,
  { reviewId, documentId }: { reviewId?: number; documentId?: number } = {}
) {
  const token = useStaffToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (variables: TVariables) => run(variables, token as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["staff", "reviews"] });
      queryClient.invalidateQueries({ queryKey: ["staff", "documents"] });
      if (reviewId !== undefined) {
        queryClient.invalidateQueries({ queryKey: ["staff", "review", reviewId] });
      }
      if (documentId !== undefined) {
        queryClient.invalidateQueries({ queryKey: ["staff", "document", documentId] });
        queryClient.invalidateQueries({ queryKey: ["staff", "audit", documentId] });
      }
    }
  });
}

export function useOpenStaffReview() {
  return useReviewMutation((documentId: number, token) => openStaffReview(documentId, token));
}

export function useAssignStaffReview(reviewId: number) {
  return useReviewMutation((_: void, token) => assignStaffReview(reviewId, token), {
    reviewId
  });
}

export function useDecideStaffReview(reviewId: number, documentId?: number) {
  return useReviewMutation(
    (payload: ReviewDecision, token) => decideStaffReview(reviewId, payload, token),
    { reviewId, documentId }
  );
}

export function useWithdrawStaffDocument(documentId: number) {
  return useReviewMutation(
    (reason: string, token) => withdrawStaffDocument(documentId, reason, token),
    { documentId }
  );
}

export function useArchiveStaffDocument(documentId: number) {
  return useReviewMutation(
    (reason: string, token) => archiveStaffDocument(documentId, reason, token),
    { documentId }
  );
}

// --- Organisations ----------------------------------------------------------

export function useStaffOrganizations() {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "organizations", token],
    queryFn: ({ signal }) => listStaffOrganizations(token as string, signal),
    enabled: Boolean(token)
  });
}

export function useStaffOrganization(organizationId: number) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "organization", organizationId, token],
    queryFn: ({ signal }) => getStaffOrganization(organizationId, token as string, signal),
    enabled: Boolean(token) && Number.isFinite(organizationId)
  });
}

export function useOrganizationMembers(organizationId: number) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "members", organizationId, token],
    queryFn: ({ signal }) => listOrganizationMembers(organizationId, token as string, signal),
    enabled: Boolean(token) && Number.isFinite(organizationId)
  });
}

export function useOrganizationQuotas(organizationId: number) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "quotas", organizationId, token],
    queryFn: ({ signal }) => listOrganizationQuotas(organizationId, token as string, signal),
    enabled: Boolean(token) && Number.isFinite(organizationId)
  });
}

export function useOrganizationReport(
  organizationId: number,
  period: { from?: string; to?: string }
) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "report", organizationId, period, token],
    queryFn: ({ signal }) =>
      getOrganizationReport(organizationId, period, token as string, signal),
    enabled: Boolean(token) && Number.isFinite(organizationId)
  });
}

function useOrganizationMutation<TVariables, TResult>(
  run: (variables: TVariables, token: string) => Promise<TResult>,
  organizationId: number
) {
  const token = useStaffToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (variables: TVariables) => run(variables, token as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["staff", "members", organizationId] });
      queryClient.invalidateQueries({ queryKey: ["staff", "organization", organizationId] });
    }
  });
}

export function useAddOrganizationMember(organizationId: number) {
  return useOrganizationMutation(
    (payload: { email: string; role: string }, token) =>
      addOrganizationMember(organizationId, payload, token),
    organizationId
  );
}

export function useSuspendOrganizationMember(organizationId: number) {
  return useOrganizationMutation(
    ({ membershipId, reason }: { membershipId: number; reason: string }, token) =>
      suspendOrganizationMember(organizationId, membershipId, reason, token),
    organizationId
  );
}

export function useEndOrganizationMember(organizationId: number) {
  return useOrganizationMutation(
    ({ membershipId, reason }: { membershipId: number; reason: string }, token) =>
      endOrganizationMember(organizationId, membershipId, reason, token),
    organizationId
  );
}

// --- Support ----------------------------------------------------------------

export function useStaffTickets(filters: StaffTicketFilters) {
  const token = useStaffToken();
  return useQuery({
    queryKey: ["staff", "tickets", filters, token],
    queryFn: ({ signal }) => listStaffTickets({ token: token as string, filters, signal }),
    enabled: Boolean(token)
  });
}

function useTicketMutation<TVariables, TResult>(
  run: (variables: TVariables, token: string) => Promise<TResult>
) {
  const token = useStaffToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (variables: TVariables) => run(variables, token as string),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["staff", "tickets"] })
  });
}

export function useAssignStaffTicket() {
  return useTicketMutation((ticketId: number, token) => assignStaffTicket(ticketId, token));
}

export function useResolveStaffTicket() {
  return useTicketMutation(
    ({ ticketId, summary }: { ticketId: number; summary: string }, token) =>
      resolveStaffTicket(ticketId, summary, token)
  );
}
