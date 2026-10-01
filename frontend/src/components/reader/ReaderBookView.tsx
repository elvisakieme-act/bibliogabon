import { useCallback, useEffect, useRef } from "react";

import { useMediaQuery } from "@/hooks/useMediaQuery";
import { ReaderPageSurface } from "@/components/reader/ReaderPageSurface";
import { ReaderPageTurn } from "@/components/reader/ReaderPageTurn";
import { leadingPage, spreadOfPage, toSpreads } from "@/components/reader/spreads";
import type { IiifManifest } from "@/features/reader/manifest";

/**
 * Le document en double page, qu'on tourne.
 *
 * Sa mécanique n'est pas celle du défilement, et c'est voulu : trois sens de
 * lecture avaient été livrés en partageant un seul mécanisme, et aucun des
 * trois ne fonctionnait. Ici il n'y a pas de défilement — un état, une double
 * page, une transition.
 *
 * La double page est **ajustée à la hauteur** : les deux pages sont entières,
 * toujours, parce qu'un livre ouvert se regarde d'un coup. Le zoom déborde
 * alors du cadre, et le conteneur défile dans les deux axes.
 *
 * Sur un écran étroit, une seule page est montrée : deux pages sur 390 px ne
 * sont pas lisibles, et un mode qui prétend l'être ment. On tourne toujours,
 * page par page — le geste reste celui du livre.
 */
const NARROW = 768;

export function ReaderBookView({
  sessionKey,
  manifest,
  zoom,
  pageNumber,
  onVisiblePage
}: {
  sessionKey: string;
  manifest: IiifManifest;
  zoom: number;
  pageNumber: number;
  onVisiblePage(pageNumber: number): void;
}) {
  const spreads = toSpreads(manifest.items);
  const narrow = useMediaQuery(`(max-width: ${NARROW - 1}px)`);
  const index = narrow
    ? Math.max(
        0,
        manifest.items.findIndex((canvas) => Number(canvas.id.split("/").pop()) === pageNumber)
      )
    : spreadOfPage(spreads, pageNumber);

  const shown = narrow
    ? [manifest.items[index]].filter(Boolean)
    : [spreads[index]?.left, spreads[index]?.right].filter(
        (canvas): canvas is NonNullable<typeof canvas> => Boolean(canvas)
      );

  // La double page annonce sa première page : c'est elle qui est enregistrée
  // comme progression, et qui s'affiche dans la barre.
  const announced = useRef<number | null>(null);
  useEffect(() => {
    const first = narrow
      ? Number(manifest.items[index]?.id.split("/").pop())
      : leadingPage(spreads[index] ?? { left: null, right: null });
    if (first && first !== announced.current && first !== pageNumber) {
      announced.current = first;
      onVisiblePage(first);
    }
  }, [index, narrow, manifest.items, spreads, pageNumber, onVisiblePage]);

  // Tourner, c'est passer à la double suivante — pas à la page suivante.
  // Avancer d'une page désynchroniserait l'appariement : la page qui était à
  // droite passerait à gauche, et tout le document se lirait décalé.
  const total = narrow ? manifest.items.length : spreads.length;
  const tourner = useCallback(
    (pas: 1 | -1) => {
      const cible = Math.min(Math.max(index + pas, 0), total - 1);
      if (cible === index) return;
      const canvas = narrow
        ? manifest.items[cible]
        : (spreads[cible]?.left ?? spreads[cible]?.right);
      const page = canvas ? Number(canvas.id.split("/").pop()) : null;
      if (page) {
        announced.current = page;
        onVisiblePage(page);
      }
    },
    [index, total, narrow, manifest.items, spreads, onVisiblePage]
  );

  // Un glissement franc tourne la page : c'est le geste du doigt sur un
  // écran tactile, et il doit exister sans viser une flèche.
  const swipe = useRef<number | null>(null);

  if (shown.length === 0) return null;

  // La largeur de la double se déduit de la hauteur disponible et du rapport
  // de chaque page : c'est la hauteur qui commande, pas la largeur, sinon une
  // page de format inhabituel sortirait du cadre par le bas.
  const ratio = shown.reduce((total, canvas) => total + canvas.width / canvas.height, 0);

  return (
    // Les flèches et les coins vivent dans ce cadre, qui ne défile pas. Placés
    // dans le conteneur de défilement, ils s'en allaient avec la page dès que
    // le zoom la faisait dépasser : on perdait de quoi tourner au moment où on
    // regardait de plus près.
    <div className="relative h-full">
      <div
        // `tabIndex` : sans lui, les flèches du clavier ne tournent pas tant
        // qu'on n'a pas cliqué dans la page.
        tabIndex={0}
        aria-label="Document"
        onKeyDown={(event) => {
          if (event.key === "ArrowRight" || event.key === "PageDown") {
            event.preventDefault();
            tourner(1);
          } else if (event.key === "ArrowLeft" || event.key === "PageUp") {
            event.preventDefault();
            tourner(-1);
          }
        }}
        onPointerDown={(event) => {
          swipe.current = event.pointerType === "mouse" ? null : event.clientX;
        }}
        onPointerUp={(event) => {
          if (swipe.current === null) return;
          const travelled = event.clientX - swipe.current;
          swipe.current = null;
          if (Math.abs(travelled) > 60) tourner(travelled < 0 ? 1 : -1);
        }}
        className="flex h-full overflow-auto bg-[var(--navy-soft)] p-4 focus-visible:outline-none sm:p-6"
      >
        {/* `m-auto` et non `items-center justify-center` : centré tant qu'il y a
          de la place, et sans marge dès qu'il n'y en a plus. Centré par
          `justify-center`, le haut et la gauche de la double page devenaient
          inatteignables dès que le zoom la faisait dépasser. */}
        <div
          aria-live="polite"
          className="m-auto flex shrink-0 gap-px shadow-editorial-lg"
          style={{ height: `${Math.round(100 * zoom)}%`, aspectRatio: ratio }}
        >
          {shown.map((canvas, position) => (
            <div
              key={canvas.id}
              className="h-full min-w-0 flex-1"
              style={
                shown.length === 2
                  ? {
                      // Le creux de la reliure : c'est ce pli au centre qui fait
                      // lire deux pages comme un livre plutôt que comme deux
                      // images posées côte à côte.
                      boxShadow:
                        position === 0
                          ? "inset -14px 0 22px -18px rgba(0,0,0,0.55)"
                          : "inset 14px 0 22px -18px rgba(0,0,0,0.55)"
                    }
                  : undefined
              }
            >
              <ReaderPageSurface canvas={canvas} sessionKey={sessionKey} enabled />
            </div>
          ))}
        </div>
      </div>

      <ReaderPageTurn
        corners
        canGoBack={index > 0}
        canGoForward={index < total - 1}
        onPrevious={() => tourner(-1)}
        onNext={() => tourner(1)}
      />
    </div>
  );
}
