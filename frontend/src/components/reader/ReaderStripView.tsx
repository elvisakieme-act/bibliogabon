import { useCallback, useEffect, useRef, useState } from "react";

import { ReaderPageSurface } from "@/components/reader/ReaderPageSurface";
import { ReaderPageTurn } from "@/components/reader/ReaderPageTurn";
import {
  centredPage,
  pageHeightInStrip,
  stripSidePadding
} from "@/components/reader/stripLayout";
import { usePagePreload } from "@/components/reader/usePagePreload";
import {
  canvasPageNumber,
  type IiifCanvas,
  type IiifManifest
} from "@/features/reader/manifest";

/**
 * Le document en défilement horizontal : une bande de pages, qu'on parcourt
 * de gauche à droite.
 *
 * Sa mécanique est la sienne. Les trois sens de lecture livrés la première fois
 * partageaient un seul mécanisme — déplacer et agrandir une image — et
 * « horizontal » ne différait alors de « vertical » que par l'endroit où les
 * pages étaient posées : trois noms, un comportement, et aucun des trois servi.
 *
 * Trois choses le distinguent vraiment du défilement vertical, et ce sont elles
 * qui font le mode :
 *
 *  - la page tient **entière** à l'écran, comme une diapositive, là où le
 *    vertical ajuste à une largeur de lecture confortable et laisse la page
 *    dépasser en bas ;
 *  - le défilement **s'arrête sur une page** (`scroll-snap`) au lieu de
 *    s'immobiliser entre deux, car une bande arrêtée à cheval sur deux pages ne
 *    se lit pas ;
 *  - la page lue est celle **au centre**, et non la plus visible : plusieurs
 *    pages entières tiennent côte à côte sur un écran large.
 *
 * Et puisqu'on avance d'une page à la fois, les flèches ont ici un sens : aux
 * extrêmes gauche et droite, à mi-hauteur, comme en double page. Le défilement
 * vertical n'en a pas — on y fait défiler.
 */
interface Box {
  width: number;
  height: number;
}

export function ReaderStripView({
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
  // Le conteneur est tenu en état et non en référence : les pages ont besoin de
  // le désigner comme racine d'observation, et une référence encore vide au
  // premier rendu ne provoquerait aucun second rendu pour la corriger.
  const [scroller, setScroller] = useState<HTMLDivElement | null>(null);
  const box = useContentBox(scroller);
  const reported = useCenteredPage(scroller, box, onVisiblePage);
  const index = Math.max(
    0,
    manifest.items.findIndex((canvas) => canvasPageNumber(canvas) === pageNumber)
  );

  // Une seule voie pour toute navigation — barre du haut, flèches, clavier :
  // on annonce la page, et l'effet ci-dessous l'amène sous les yeux. Deux voies
  // auraient fini par se contredire.
  const tourner = useCallback(
    (pas: 1 | -1) => {
      // On demande la page voisine, et on ne fait rien s'il n'y en a pas.
      // Borner l'indice puis lire la liste revenait au même tant que la borne
      // était juste, mais une borne oubliée désignait une page absente — et au
      // bout du document, le clavier faisait tomber le lecteur.
      const voisine = manifest.items[index + pas];
      if (!voisine) return;
      onVisiblePage(canvasPageNumber(voisine));
    },
    [index, manifest.items, onVisiblePage]
  );

  // Rien à faire si c'est le défilement lui-même qui vient d'annoncer la page,
  // sinon la vue se recalerait sans cesse sur ce qu'on est déjà en train de
  // lire.
  useEffect(() => {
    if (reported.current === pageNumber) return;
    const target = scroller?.querySelector(`[data-page="${pageNumber}"]`);
    target?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
  }, [pageNumber, reported, scroller]);

  return (
    // Les flèches vivent dans ce cadre, qui ne défile pas. Placées dans le
    // conteneur de défilement, elles s'en iraient avec les pages dès le premier
    // geste — et la bande défile toujours.
    <div className="relative h-full">
      <div
        ref={setScroller}
        // `tabIndex` : sans lui, le clavier ne fait rien tant qu'on n'a pas
        // cliqué dans la page.
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
          // Haut et bas restent au navigateur : quand le zoom fait dépasser la
          // page, c'est ainsi qu'on la parcourt.
        }}
        // `snap-mandatory` sans condition : une page agrandie devient plus large
        // que la fenêtre, et la règle CSS veut qu'une zone d'arrêt plus grande
        // que le conteneur se parcoure librement. Le zoom ne rend donc aucun
        // bord inatteignable.
        className="flex h-full snap-x snap-mandatory overflow-auto bg-[var(--navy-soft)] p-4 focus-visible:outline-none sm:p-6"
      >
        {/* `m-auto` et non `items-center justify-center` : centré tant qu'il y a
            de la place, et sans marge dès qu'il n'y en a plus. Centré par
            `justify-center`, le début de la bande devenait inatteignable dès
            qu'elle dépassait la largeur du conteneur. */}
        <div
          className="m-auto flex w-max shrink-0 items-center gap-6"
          style={{
            // De quoi amener la première et la dernière page au centre, elles
            // aussi. Sans cet espace, le défilement s'arrêtait avant et la page
            // lue à l'ouverture était la deuxième.
            paddingInlineStart: stripSidePadding(box, manifest.items[0], zoom),
            paddingInlineEnd: stripSidePadding(
              box,
              manifest.items[manifest.items.length - 1],
              zoom
            )
          }}
        >
          {manifest.items.map((canvas) => (
            <StripPage
              key={canvasPageNumber(canvas)}
              canvas={canvas}
              sessionKey={sessionKey}
              scroller={scroller}
              height={pageHeightInStrip(box, canvas, zoom)}
            />
          ))}
        </div>
      </div>

      {/* Pas de coins à tirer ici : on tire un coin pour tourner une feuille, et
          une bande ne se feuillette pas. */}
      <ReaderPageTurn
        corners={false}
        canGoBack={index > 0}
        canGoForward={index < manifest.items.length - 1}
        onPrevious={() => tourner(-1)}
        onNext={() => tourner(1)}
      />
    </div>
  );
}

/**
 * La place réellement offerte aux pages.
 *
 * Le rembourrage est retiré : `clientWidth` l'inclut, et une page calculée
 * dessus dépassait de 32 px sur un téléphone — juste assez pour ne plus tenir.
 */
function useContentBox(scroller: HTMLElement | null): Box {
  const [box, setBox] = useState<Box>({ width: 0, height: 0 });

  useEffect(() => {
    if (!scroller) return;
    const measure = () => {
      const style = window.getComputedStyle(scroller);
      const horizontal = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
      const vertical = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      setBox({
        width: Math.max(0, scroller.clientWidth - (horizontal || 0)),
        height: Math.max(0, scroller.clientHeight - (vertical || 0))
      });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(scroller);
    return () => observer.disconnect();
  }, [scroller]);

  return box;
}

/**
 * La page qu'on lit, prise sur la position de défilement.
 *
 * C'est la question du mode, et elle se mesure, elle ne s'observe pas : une
 * page entière reste une page entière qu'elle soit au centre ou au bord, donc
 * la part visible ne distingue rien. On mesure donc la distance au centre.
 *
 * Tant qu'aucune page n'a de largeur — avant la mise en page — on n'annonce
 * rien : annoncer la première ferait perdre sa page à qui reprend sa lecture
 * au milieu du document.
 */
function useCenteredPage(
  scroller: HTMLElement | null,
  box: Box,
  onVisiblePage: (pageNumber: number) => void
) {
  const reported = useRef<number | null>(null);
  const visibleRef = useRef(onVisiblePage);
  visibleRef.current = onVisiblePage;

  useEffect(() => {
    if (!scroller) return;
    let scheduled = false;
    const look = () => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        const frame = scroller.getBoundingClientRect();
        const middle = frame.left + scroller.clientWidth / 2;
        const boxes = [...scroller.querySelectorAll<HTMLElement>("[data-page]")]
          .map((element) => {
            const rect = element.getBoundingClientRect();
            return { page: Number(element.dataset.page), left: rect.left, width: rect.width };
          })
          .filter((candidate) => candidate.width > 0);
        const nearest = centredPage(middle, boxes);
        if (nearest !== null && nearest !== reported.current) {
          reported.current = nearest;
          visibleRef.current(nearest);
        }
      });
    };
    look();
    scroller.addEventListener("scroll", look, { passive: true });
    return () => scroller.removeEventListener("scroll", look);
  }, [box, scroller]);

  return reported;
}

/**
 * Une page de la bande.
 *
 * Sa hauteur lui est donnée, parce qu'elle dépend de la place offerte à toute
 * la bande ; sa largeur en découle par le rapport du manifeste. Une page de
 * format inhabituel reste donc entière, là où une largeur imposée l'aurait
 * coupée en bas.
 */
function StripPage({
  canvas,
  sessionKey,
  scroller,
  height
}: {
  canvas: IiifCanvas;
  sessionKey: string;
  scroller: Element | null;
  height: number | null;
}) {
  // L'avance se prend à droite et à gauche : c'est de ces côtés que la lecture
  // va et revient.
  const { holder, approaching } = usePagePreload({ root: scroller, margin: "0px 1400px" });

  return (
    <div
      ref={holder}
      className="shrink-0 snap-center shadow-editorial-lg"
      style={{ aspectRatio: `${canvas.width} / ${canvas.height}`, height: height ?? "100%" }}
    >
      <ReaderPageSurface canvas={canvas} sessionKey={sessionKey} enabled={approaching} />
    </div>
  );
}
