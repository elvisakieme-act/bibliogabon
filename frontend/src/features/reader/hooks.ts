import { useMutation, useQuery } from "@tanstack/react-query";

import { closeReaderSession, createReaderSession, getReaderPage } from "@/api/reader";
import { fetchReaderManifest } from "@/features/reader/manifest";
import { fetchReaderPageImage } from "@/features/reader/pageImage";
import { useAuth } from "@/auth/useAuth";

export function useCreateReaderSession() {
  const { tokens } = useAuth();
  return useMutation({
    mutationFn: (documentId: number | string) => createReaderSession(documentId, tokens?.access)
  });
}

/**
 * Une page du lecteur.
 *
 * `enabled` permet à un emplacement de page de différer sa requête jusqu'à ce
 * qu'il approche de l'écran : en défilement continu, demander les 157 pages
 * d'un cours à l'ouverture inonderait le serveur et la connexion du lecteur.
 */
export function useReaderPage(sessionKey: string | null, pageNumber: number, enabled = true) {
  const { tokens } = useAuth();
  return useQuery({
    queryKey: ["reader-page", sessionKey, pageNumber, tokens?.access ?? null],
    queryFn: () => getReaderPage(sessionKey as string, pageNumber, tokens?.access),
    enabled: Boolean(sessionKey) && enabled,
    // Une page déjà lue ne change pas pendant la session : la relire ferait
    // une requête et une ligne de journal de plus pour rien.
    staleTime: Infinity
  });
}

export function useCloseReaderSession() {
  const { tokens } = useAuth();
  return useMutation({
    mutationFn: (sessionKey: string) => closeReaderSession(sessionKey, tokens?.access)
  });
}

/**
 * L'image d'une page, sous forme de `Blob`.
 *
 * C'est le `Blob` qui est mis en cache, pas l'adresse `blob:` — cette dernière
 * doit être créée et révoquée par le composant qui l'affiche. Mettre l'adresse
 * en cache ferait survivre une URL déjà révoquée, et la page réapparaîtrait
 * vide au retour en arrière.
 */
export function useReaderPageImage(path: string | null, enabled = true) {
  const { tokens, isHydrating } = useAuth();
  return useQuery({
    queryKey: ["reader-page-image", path, tokens?.access ?? null],
    queryFn: () => fetchReaderPageImage(path as string, tokens?.access),
    // Tant que la session n'est pas hydratée, le jeton n'est pas connu : une
    // requête partie trop tôt reviendrait en 403 et le lecteur afficherait
    // brièvement une erreur avant de réessayer.
    enabled: Boolean(path) && enabled && !isHydrating,
    staleTime: Infinity,
    retry: false
  });
}

/** Manifeste IIIF de la session : une requête pour tout le document. */
export function useReaderManifest(sessionKey: string | null) {
  const { tokens, isHydrating } = useAuth();
  return useQuery({
    queryKey: ["reader-manifest", sessionKey, tokens?.access ?? null],
    queryFn: () => fetchReaderManifest(sessionKey as string, tokens?.access),
    enabled: Boolean(sessionKey) && !isHydrating,
    staleTime: Infinity,
    retry: false
  });
}
