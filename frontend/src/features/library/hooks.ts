import {
  useInfiniteQuery,
  useMutation,
  useQueryClient
} from "@tanstack/react-query";

import {
  addFavorite,
  listFavorites,
  listReadingProgress,
  removeFavorite,
  updateReadingProgress
} from "@/api/library";
import { useAuth } from "@/auth/AuthProvider";

function requireAccessToken(access?: string | null) {
  if (!access) throw new Error("Authentication is required.");
  return access;
}

export function useFavorites() {
  const { tokens } = useAuth();
  return useInfiniteQuery({
    queryKey: ["favorites", tokens?.access ?? null],
    queryFn: ({ pageParam }) =>
      listFavorites(requireAccessToken(tokens?.access), pageParam),
    initialPageParam: 1,
    getNextPageParam: (lastPage, pages) =>
      lastPage.next ? pages.length + 1 : undefined,
    enabled: Boolean(tokens?.access)
  });
}

export function useAddFavorite() {
  const { tokens } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: number | string) =>
      addFavorite(requireAccessToken(tokens?.access), documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] })
  });
}

export function useRemoveFavorite() {
  const { tokens } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: number | string) =>
      removeFavorite(requireAccessToken(tokens?.access), documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] })
  });
}

export function useReadingProgress() {
  const { tokens } = useAuth();
  return useInfiniteQuery({
    queryKey: ["reading-progress", tokens?.access ?? null],
    queryFn: ({ pageParam }) =>
      listReadingProgress(requireAccessToken(tokens?.access), pageParam),
    initialPageParam: 1,
    getNextPageParam: (lastPage, pages) =>
      lastPage.next ? pages.length + 1 : undefined,
    enabled: Boolean(tokens?.access)
  });
}

export function useUpdateReadingProgress() {
  const { tokens } = useAuth();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { documentId: number | string; lastPageNumber: number }) =>
      updateReadingProgress(
        requireAccessToken(tokens?.access),
        input.documentId,
        input.lastPageNumber
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["reading-progress"] })
  });
}
