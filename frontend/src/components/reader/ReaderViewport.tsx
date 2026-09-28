import { useEffect, useMemo, useRef } from "react";

import { ReaderPageSlot } from "@/components/reader/ReaderPageSlot";
import { useVisiblePage } from "@/components/reader/useVisiblePage";
import type { ScrollMode } from "@/components/reader/readerPreferences";

/**
 * Les trois sens de lecture.
 *
 * - **Vertical** — les pages s'enchaînent, on fait défiler. C'est le mode de
 *   lecture longue, et celui d'un écran d'ordinateur.
 * - **Horizontal** — une page à la fois, on glisse de côté. C'est le geste
 *   naturel sur téléphone, et l'aimantation évite de s'arrêter entre deux
 *   pages.
 * - **Livre** — deux pages côte à côte, reliure au centre. La transition est
 *   un glissement franc plutôt qu'une animation de page qui se tourne : la
 *   seconde est spectaculaire mais coûteuse, et le public visé lit en grande
 *   partie sur des téléphones d'entrée de gamme.
 *
 * Le zoom agit sur la **largeur** de la page, jamais par `transform: scale`.
 * Une mise à l'échelle agrandirait la page sans agrandir la zone de
 * défilement : les bords deviendraient inatteignables dès qu'on dépasse
 * 100 %.
 */
export function ReaderViewport({
  sessionKey,
  title,
  pageCount,
  pageNumber,
  mode,
  zoom,
  onVisiblePage
}: {
  sessionKey: string | null;
  title: string;
  pageCount: number;
  pageNumber: number;
  mode: ScrollMode;
  zoom: number;
  onVisiblePage(pageNumber: number): void;
}) {
  const report = useVisiblePage(onVisiblePage);
  const pages = useMemo(
    () => Array.from({ length: pageCount }, (unused, index) => index + 1),
    [pageCount]
  );
  const width = { maxWidth: `${Math.round(52 * zoom)}rem` };

  if (mode === "livre") {
    return (
      <BookSpread
        sessionKey={sessionKey}
        title={title}
        pageCount={pageCount}
        pageNumber={pageNumber}
        zoom={zoom}
      />
    );
  }

  if (mode === "horizontal") {
    return (
      <HorizontalStrip
        sessionKey={sessionKey}
        title={title}
        pages={pages}
        pageNumber={pageNumber}
        zoom={zoom}
        onVisiblePage={report}
      />
    );
  }

  return (
    <div className="h-full overflow-y-auto overflow-x-hidden bg-[var(--navy-soft)] px-3 py-6 sm:px-6">
      <div className="mx-auto flex flex-col gap-6" style={width}>
        {pages.map((number) => (
          <ReaderPageSlot
            key={number}
            sessionKey={sessionKey}
            pageNumber={number}
            title={title}
            onVisible={report}
          />
        ))}
      </div>
    </div>
  );
}

function HorizontalStrip({
  sessionKey,
  title,
  pages,
  pageNumber,
  zoom,
  onVisiblePage
}: {
  sessionKey: string | null;
  title: string;
  pages: number[];
  pageNumber: number;
  zoom: number;
  onVisiblePage(pageNumber: number, ratio: number): void;
}) {
  const strip = useRef<HTMLDivElement>(null);

  // La barre du haut navigue aussi en mode horizontal : le défilement doit
  // suivre la page demandée, sans quoi les flèches ne feraient rien de
  // visible.
  useEffect(() => {
    const target = strip.current?.querySelector(`[data-page="${pageNumber}"]`);
    target?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [pageNumber]);

  return (
    <div
      ref={strip}
      className="flex h-full snap-x snap-mandatory items-center gap-6 overflow-x-auto overflow-y-hidden bg-[var(--navy-soft)] px-[max(1rem,calc(50%-26rem))] py-6"
    >
      {pages.map((number) => (
        <div
          key={number}
          className="h-full shrink-0 snap-center overflow-y-auto"
          style={{ width: `${Math.round(48 * zoom)}rem`, maxWidth: "92vw" }}
        >
          <ReaderPageSlot
            sessionKey={sessionKey}
            pageNumber={number}
            title={title}
            onVisible={onVisiblePage}
          />
        </div>
      ))}
    </div>
  );
}

function BookSpread({
  sessionKey,
  title,
  pageCount,
  pageNumber,
  zoom
}: {
  sessionKey: string | null;
  title: string;
  pageCount: number;
  pageNumber: number;
  zoom: number;
}) {
  // La première page est une couverture : elle se présente seule, comme un
  // livre qu'on ouvre. Les suivantes vont par paires (2-3, 4-5, …), ce qui
  // place les pages paires à gauche — la convention de l'imprimé.
  const left = pageNumber <= 1 ? null : pageNumber % 2 === 0 ? pageNumber : pageNumber - 1;
  const right = left === null ? 1 : left + 1 <= pageCount ? left + 1 : null;
  const pages = [left, right].filter((value): value is number => value !== null);

  // Une page seule est centrée, à la largeur d'une demi-double-page. Réserver
  // la moitié vide décalait la couverture sur le côté, comme si une page
  // manquait.
  const spreadWidth = `${Math.round((pages.length === 2 ? 72 : 36) * zoom)}rem`;

  return (
    <div className="flex h-full items-center justify-center overflow-auto bg-[var(--navy-soft)] p-4 sm:p-8">
      <div
        className="flex w-full items-start justify-center gap-px"
        style={{ maxWidth: spreadWidth }}
      >
        {pages.map((number, index) => (
          <div
            key={number}
            className="min-w-0 flex-1"
            style={
              pages.length === 2
                ? {
                    // L'ombre de reliure, portée vers l'intérieur : c'est ce
                    // creux central qui fait lire deux pages comme un livre
                    // plutôt que comme deux images côte à côte.
                    boxShadow:
                      index === 0
                        ? "8px 0 18px -12px rgba(0,0,0,0.5)"
                        : "-8px 0 18px -12px rgba(0,0,0,0.5)"
                  }
                : undefined
            }
          >
            <ReaderPageSlot sessionKey={sessionKey} pageNumber={number} title={title} />
          </div>
        ))}
      </div>
    </div>
  );
}
