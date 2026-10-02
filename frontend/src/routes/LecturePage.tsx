import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "@tanstack/react-router";

import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/useAuth";
import { ReaderBookView } from "@/components/reader/ReaderBookView";
import { ReaderDisplayOptions } from "@/components/reader/ReaderDisplayOptions";
import { ReaderPage } from "@/components/reader/ReaderPage";
import { ReaderStripView } from "@/components/reader/ReaderStripView";
import { ReaderToolbar } from "@/components/reader/ReaderToolbar";
import { ReaderViewport } from "@/components/reader/ReaderViewport";
import {
  DEFAULT_MODE,
  DEFAULT_ZOOM,
  nextZoom,
  readMode,
  readZoom,
  writeMode,
  writeZoom,
  type ReadingMode
} from "@/components/reader/readerPreferences";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { useSettledValue } from "@/hooks/useSettledValue";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocument } from "@/features/catalog/hooks";
import { useUpdateReadingProgress } from "@/features/library/hooks";
import {
  useCloseReaderSession,
  useCreateReaderSession,
  useReaderManifest,
  useReaderPage
} from "@/features/reader/hooks";

function readerErrorStatus(error: unknown) {
  return error instanceof ApiError ? error.status : null;
}

/**
 * Le temps qu'une page doit rester sous les yeux pour compter comme lue.
 *
 * Assez court pour qu'une pause de lecture l'enregistre, assez long pour qu'un
 * parcours rapide ne laisse aucune trace. Une seconde et demie : on tourne
 * trois pages par seconde en cherchant un passage, et l'on s'arrête plus
 * longtemps dès qu'on lit une ligne.
 */
const PROGRESS_SETTLE_MS = 1500;

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
  // Une requête décrit tout le document : nombre de pages, dimensions,
  // service d'images. Sans elle, ouvrir un cours de 157 pages demanderait 157
  // `info.json` — et journaliserait le document entier comme lu.
  const manifest = useReaderManifest(sessionKey);
  // La page retenue est celle sur laquelle la lecture **s'arrête**, jamais
  // celle qu'on traverse en cherchant un passage.
  const settledPage = useSettledValue(pageNumber, PROGRESS_SETTLE_MS);
  const [optionsOpen, setOptionsOpen] = useState(false);
  // Lu une seule fois : `localStorage` peut échouer, et le relire à chaque
  // rendu transformerait un stockage refusé en boucle de rendus.
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const [mode, setMode] = useState<ReadingMode>(DEFAULT_MODE);

  useEffect(() => {
    setZoom(readZoom());
    setMode(readMode());
  }, []);

  const applyMode = useCallback((value: ReadingMode) => {
    setMode(value);
    writeMode(value);
  }, []);

  const applyZoom = useCallback((direction: 1 | -1) => {
    setZoom((current) => {
      const value = nextZoom(current, direction);
      writeZoom(value);
      return value;
    });
  }, []);

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

  /**
   * La progression est l'endroit où l'on **s'est arrêté**, pas chacun de ceux
   * qu'on a survolés.
   *
   * Elle s'écrivait à chaque page traversée : mesuré, douze pages parcourues
   * au clavier déclenchaient seize écritures. Le défilement horizontal l'a
   * rendu voyant — on y traverse un cours de 157 pages en quelques secondes —
   * mais le vertical faisait de même.
   *
   * Ce n'est donc pas qu'une économie de requêtes : reprendre une lecture à la
   * dernière page *aperçue* en cherchant un passage ramène le lecteur là où il
   * n'a jamais lu. On attend que la page se pose.
   */
  const enregistrerProgression = useCallback(
    (lastPageNumber: number) => {
      const persistedPageKey = `${documentId}:${lastPageNumber}`;
      if (persistedPageRef.current === persistedPageKey) return;
      persistedPageRef.current = persistedPageKey;
      updateProgressMutate({ documentId, lastPageNumber });
    },
    [documentId, updateProgressMutate]
  );

  useEffect(() => {
    if (!tokens?.access || !page.data || settledPage === null) return;
    enregistrerProgression(settledPage);
  }, [enregistrerProgression, page.data, settledPage, tokens?.access]);

  // À la sortie, la page en cours part même si elle n'a pas eu le temps de se
  // poser : quitter le lecteur dans l'intervalle ne doit pas perdre la page,
  // sans quoi le remède coûterait plus que le mal. Les conditions passent par
  // des références, afin que ce nettoyage ne soit **que** celui du démontage —
  // dépendre des valeurs le ferait tirer à chaque changement de page, et l'on
  // serait revenu au point de départ.
  const sortieRef = useRef<() => void>(() => {});
  sortieRef.current = () => {
    if (!tokens?.access || !page.data) return;
    enregistrerProgression(pageNumber);
  };
  useEffect(() => () => sortieRef.current(), []);

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
            description="Connectez-vous pour accéder à ce document."
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
            title="Accès requis"
            description="Un droit de lecture actif est nécessaire pour ce document."
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
            description="La page ne peut pas être chargée pour le moment."
          />
          <button
            type="button"
            onClick={() => void startSession()}
            className="mt-6 rounded-lg bg-[var(--navy)] px-5 py-3 text-sm font-semibold text-white"
          >
            Réessayer
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

  // Trois composants, trois mécaniques, une seule signature. Les faire
  // partager le *mécanisme* les avait cassés tous les trois : le défilement
  // vertical veut un conteneur qui défile en hauteur, l'horizontal une bande
  // qui s'arrête sur une page, la double page aucun défilement mais un état
  // qu'on tourne.
  const ReaderView =
    mode === "livre"
      ? ReaderBookView
      : mode === "horizontal"
        ? ReaderStripView
        : ReaderViewport;

  return (
    // Plein écran : un document se lit dans le document, pas dans une colonne
    // au milieu d'un site. `h-dvh` et non `h-screen` — sur mobile, la barre du
    // navigateur mange une partie de `100vh` et la barre d'outils du lecteur
    // se retrouverait hors de l'écran.
    <div className="fixed inset-0 z-50 flex h-dvh flex-col bg-[var(--navy-soft)]">
      <ReaderToolbar
        pageNumber={pageNumber}
        pageCount={pageCount}
        onClose={() => void returnToDocument()}
        onOpenOptions={() => setOptionsOpen(true)}
      />

      <ReaderDisplayOptions
        open={optionsOpen}
        mode={mode}
        zoom={zoom}
        onClose={() => setOptionsOpen(false)}
        onModeChange={applyMode}
        onZoomChange={applyZoom}
      />

      <div className="min-h-0 flex-1">
        {manifest.data && manifest.data.items.length > 0 && sessionKey ? (
          <ReaderView
            sessionKey={sessionKey}
            manifest={manifest.data}
            zoom={zoom}
            pageNumber={pageNumber}
            onVisiblePage={setPageNumber}
          />
        ) : manifest.isPending ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-[var(--muted-foreground)]">Ouverture du document…</p>
          </div>
        ) : (
          // Repli texte : un document ingéré avant le tuilage, ou dont le
          // rendu a échoué, doit rester lisible. Le perdre ferait d'une
          // amélioration d'affichage une perte d'accès.
          <div className="h-full overflow-y-auto px-4 py-6">
            <div className="mx-auto max-w-3xl">
              <ReaderPage title={document.data?.title ?? "Lecture"} page={page.data} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
