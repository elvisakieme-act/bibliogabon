import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "@tanstack/react-router";

import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/useAuth";
import { ReaderToolbar } from "@/components/reader/ReaderToolbar";
import { ReaderViewport } from "@/components/reader/ReaderViewport";
import {
  DEFAULT_MODE,
  DEFAULT_ZOOM,
  nextZoom,
  readPreferences,
  writePreferences,
  type ScrollMode
} from "@/components/reader/readerPreferences";
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
  // **La page d'amorçage, pas la page courante.** Elle donne le nombre de
  // pages et fait remonter les refus d'accès ; elle ne suit pas la navigation.
  // La faire suivre `pageNumber` démontait le lecteur entier à chaque
  // changement de page — et, en défilement continu, le remontage rappelait
  // l'observateur qui changeait la page, donc le lecteur oscillait sans
  // jamais se stabiliser.
  const page = useReaderPage(sessionKey, initialPageNumber);
  // Lues une seule fois : `localStorage` peut échouer, et le relire à chaque
  // rendu transformerait un stockage refusé en boucle de rendus.
  const [mode, setMode] = useState<ScrollMode>(DEFAULT_MODE);
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);

  useEffect(() => {
    const stored = readPreferences();
    setMode(stored.mode);
    setZoom(stored.zoom);
  }, []);

  const applyMode = useCallback((value: ScrollMode) => {
    setMode(value);
    setZoom((current) => {
      writePreferences({ mode: value, zoom: current });
      return current;
    });
  }, []);

  const applyZoom = useCallback(
    (direction: 1 | -1) => {
      setZoom((current) => {
        const value = nextZoom(current, direction);
        writePreferences({ mode, zoom: value });
        return value;
      });
    },
    [mode]
  );

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
  }, [closeSessionMutate, createSessionMutateAsync, documentId, initialPageNumber]);

  useEffect(() => {
    void startSession();
    return endSession;
  }, [endSession, startSession]);

  useEffect(() => {
    // La progression suit la page **lue**, que le lecteur y soit arrivé par
    // les flèches ou en faisant défiler.
    const loadedPageNumber = page.data ? pageNumber : null;
    if (!tokens?.access || !loadedPageNumber) return;
    const persistedPageKey = `${documentId}:${loadedPageNumber}`;
    if (persistedPageRef.current === persistedPageKey) return;
    persistedPageRef.current = persistedPageKey;
    updateProgressMutate({
      documentId,
      lastPageNumber: loadedPageNumber
    });
  }, [documentId, page.data, pageNumber, tokens?.access, updateProgressMutate]);

  async function returnToDocument() {
    endSession();
    await navigate({ to: "/documents/$id", params: { id: documentId } });
  }

  const sessionErrorStatus = readerErrorStatus(createSession.error);
  const pageErrorStatus = readerErrorStatus(page.error);
  const errorStatus = sessionErrorStatus ?? pageErrorStatus;

  if (errorStatus === 401) {
    return (
      <SiteLayout>
        <main className="container-editorial py-10 sm:py-16">
          <EmptyState
            title="Connexion requise"
            description="Connectez-vous pour acceder a ce document."
          />
          <Link
            to="/connexion"
            search={{ next: `/lecture/${documentId}${location.searchStr}` }}
            className="mt-6 inline-flex rounded-lg bg-[var(--navy)] px-5 py-3 text-sm font-semibold text-white"
          >
            Se connecter
          </Link>
        </main>
      </SiteLayout>
    );
  }

  if (errorStatus === 403) {
    return (
      <SiteLayout>
        <main className="container-editorial py-10 sm:py-16">
          <EmptyState
            title="Acces requis"
            description="Un droit de lecture actif est necessaire pour ce document."
          />
        </main>
      </SiteLayout>
    );
  }

  if (errorStatus === 404) {
    return (
      <SiteLayout>
        <main className="container-editorial py-10 sm:py-16">
          <EmptyState
            title="Document introuvable"
            description="Ce document est introuvable ou indisponible."
          />
        </main>
      </SiteLayout>
    );
  }

  if (createSession.isError || page.isError) {
    return (
      <SiteLayout>
        <main className="container-editorial py-10 sm:py-16">
          <EmptyState
            title="Lecture indisponible"
            description="La page ne peut pas etre chargee pour le moment."
          />
          <button
            type="button"
            onClick={() => void startSession()}
            className="mt-6 rounded-lg bg-[var(--navy)] px-5 py-3 text-sm font-semibold text-white"
          >
            Reessayer
          </button>
        </main>
      </SiteLayout>
    );
  }

  if (createSession.isPending || !sessionKey || page.isPending || !page.data) {
    return (
      <SiteLayout>
        <main className="container-editorial py-10 sm:py-16">
          <Skeleton label="Chargement de la lecture" />
        </main>
      </SiteLayout>
    );
  }

  const pageCount = page.data.page_count;

  return (
    // Plein écran : un document se lit dans le document, pas dans une colonne
    // au milieu d'un site. `h-dvh` et non `h-screen` — sur mobile, la barre du
    // navigateur mange une partie de `100vh` et la barre d'outils du lecteur
    // se retrouverait hors de l'écran.
    <div className="fixed inset-0 z-50 flex h-dvh flex-col bg-[var(--navy-soft)]">
      <ReaderToolbar
        title={document.data?.title ?? "Lecture"}
        pageNumber={pageNumber}
        pageCount={pageCount}
        mode={mode}
        zoom={zoom}
        onModeChange={applyMode}
        onZoomChange={applyZoom}
        onPrevious={() => setPageNumber((current) => Math.max(1, current - 1))}
        onNext={() => setPageNumber((current) => Math.min(pageCount, current + 1))}
        onClose={() => void returnToDocument()}
      />
      <div className="min-h-0 flex-1">
        <ReaderViewport
          sessionKey={sessionKey}
          title={document.data?.title ?? "Lecture"}
          pageCount={pageCount}
          pageNumber={pageNumber}
          mode={mode}
          zoom={zoom}
          onVisiblePage={setPageNumber}
        />
      </div>
    </div>
  );
}
