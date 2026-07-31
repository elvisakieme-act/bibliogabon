import { useCallback, useEffect, useRef, useState } from "react";
import {
  Link,
  useLocation,
  useNavigate,
  useParams
} from "@tanstack/react-router";

import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/AuthProvider";
import { ReaderControls } from "@/components/reader/ReaderControls";
import { ReaderPage } from "@/components/reader/ReaderPage";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocument } from "@/features/catalog/hooks";
import { useUpdateReadingProgress } from "@/features/library/hooks";
import {
  useCloseReaderSession,
  useCreateReaderSession,
  useReaderPage
} from "@/features/reader/hooks";

function readerErrorStatus(error: unknown) {
  return error instanceof ApiError ? error.status : null;
}

function resumePageNumber(searchStr: string) {
  const value = Number(new URLSearchParams(searchStr).get("page") ?? 1);
  return Number.isInteger(value) && value > 0 ? value : 1;
}

export function LecturePage() {
  const { documentId } = useParams({ from: "/lecture/$documentId" });
  const location = useLocation();
  const navigate = useNavigate();
  const { tokens } = useAuth();
  const initialPageNumber = resumePageNumber(location.searchStr);
  const document = useDocument(documentId);
  const createSession = useCreateReaderSession();
  const closeSession = useCloseReaderSession();
  const updateProgress = useUpdateReadingProgress();
  const createSessionMutateAsync = createSession.mutateAsync;
  const closeSessionMutate = closeSession.mutate;
  const updateProgressMutate = updateProgress.mutate;
  const [sessionKey, setSessionKey] = useState<string | null>(null);
  const [pageNumber, setPageNumber] = useState(initialPageNumber);
  const sessionKeyRef = useRef<string | null>(null);
  const sessionGenerationRef = useRef(0);
  const persistedPageRef = useRef<string | null>(null);
  const page = useReaderPage(sessionKey, pageNumber);

  const endSession = useCallback(() => {
    sessionGenerationRef.current += 1;
    const activeSessionKey = sessionKeyRef.current;
    if (!activeSessionKey) return;
    sessionKeyRef.current = null;
    setSessionKey(null);
    closeSessionMutate(activeSessionKey);
  }, [closeSessionMutate]);

  const startSession = useCallback(async () => {
    const generation = sessionGenerationRef.current + 1;
    sessionGenerationRef.current = generation;
    const activeSessionKey = sessionKeyRef.current;
    if (activeSessionKey) {
      sessionKeyRef.current = null;
      closeSessionMutate(activeSessionKey);
    }
    setPageNumber(initialPageNumber);
    setSessionKey(null);
    try {
      const session = await createSessionMutateAsync(documentId);
      if (sessionGenerationRef.current !== generation) {
        closeSessionMutate(session.session_key);
        return;
      }
      sessionKeyRef.current = session.session_key;
      setSessionKey(session.session_key);
    } catch {
      // The mutation state supplies the route's access and retry UI.
    }
  }, [
    closeSessionMutate,
    createSessionMutateAsync,
    documentId,
    initialPageNumber
  ]);

  useEffect(() => {
    void startSession();
    return endSession;
  }, [endSession, startSession]);

  useEffect(() => {
    const loadedPageNumber = page.data?.page_number;
    if (!tokens?.access || !loadedPageNumber) return;
    const persistedPageKey = `${documentId}:${loadedPageNumber}`;
    if (persistedPageRef.current === persistedPageKey) return;
    persistedPageRef.current = persistedPageKey;
    updateProgressMutate({
      documentId,
      lastPageNumber: loadedPageNumber
    });
  }, [
    documentId,
    page.data?.page_number,
    tokens?.access,
    updateProgressMutate
  ]);

  async function returnToDocument() {
    endSession();
    await navigate({ to: "/documents/$id", params: { id: documentId } });
  }

  const sessionErrorStatus = readerErrorStatus(createSession.error);
  const pageErrorStatus = readerErrorStatus(page.error);
  const errorStatus = sessionErrorStatus ?? pageErrorStatus;

  if (errorStatus === 401) {
    return <SiteLayout><main className="container-editorial py-10 sm:py-16"><EmptyState title="Connexion requise" description="Connectez-vous pour acceder a ce document." /><Link to="/connexion" search={{ next: `/lecture/${documentId}${location.searchStr}` }} className="mt-6 inline-flex rounded-lg bg-[var(--navy)] px-5 py-3 text-sm font-semibold text-white">Se connecter</Link></main></SiteLayout>;
  }

  if (errorStatus === 403) {
    return <SiteLayout><main className="container-editorial py-10 sm:py-16"><EmptyState title="Acces requis" description="Un droit de lecture actif est necessaire pour ce document." /></main></SiteLayout>;
  }

  if (errorStatus === 404) {
    return <SiteLayout><main className="container-editorial py-10 sm:py-16"><EmptyState title="Document introuvable" description="Ce document est introuvable ou indisponible." /></main></SiteLayout>;
  }

  if (createSession.isError || page.isError) {
    return <SiteLayout><main className="container-editorial py-10 sm:py-16"><EmptyState title="Lecture indisponible" description="La page ne peut pas etre chargee pour le moment." /><button type="button" onClick={() => void startSession()} className="mt-6 rounded-lg bg-[var(--navy)] px-5 py-3 text-sm font-semibold text-white">Reessayer</button></main></SiteLayout>;
  }

  if (createSession.isPending || !sessionKey || page.isPending || !page.data) {
    return <SiteLayout><main className="container-editorial py-10 sm:py-16"><Skeleton label="Chargement de la lecture" /></main></SiteLayout>;
  }

  return (
    <SiteLayout>
      <main className="container-editorial py-8 sm:py-12">
        <button type="button" onClick={returnToDocument} className="mb-6 text-sm font-semibold text-[var(--green)] hover:underline">Retour au document</button>
        <ReaderPage title={document.data?.title ?? "Lecture"} page={page.data} />
        <div className="mt-6">
          <ReaderControls
            pageNumber={page.data.page_number}
            pageCount={page.data.page_count}
            onPrevious={() => setPageNumber((currentPage) => Math.max(1, currentPage - 1))}
            onNext={() => setPageNumber((currentPage) => Math.min(page.data.page_count, currentPage + 1))}
          />
        </div>
      </main>
    </SiteLayout>
  );
}
