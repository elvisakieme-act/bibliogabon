import { useEffect, useState } from "react";

import { ReaderPageImage } from "@/components/reader/ReaderPageImage";
import { useMostVisiblePage } from "@/components/reader/useMostVisiblePage";
import { canvasPageNumber, type IiifManifest } from "@/features/reader/manifest";

/**
 * Le document, en défilement vertical.
 *
 * C'est un défilement ordinaire, dans un conteneur qui défile vraiment : la
 * molette, le pavé tactile, le doigt, les flèches du clavier, la barre de
 * défilement et la touche Origine fonctionnent sans qu'on écrive une ligne
 * pour chacun. Pas de flèches de page ici : on avance en faisant défiler.
 *
 * La version précédente reposait sur OpenSeadragon, qui déplace et agrandit
 * une image plutôt que de faire défiler un document : la molette y zoomait,
 * et avancer dans le texte demandait de tirer la page. OpenSeadragon équipe
 * Mirador et Universal Viewer, qui montrent *une page à la fois* — c'est son
 * cas d'usage, et ce n'était pas le nôtre.
 *
 * Le zoom agit sur la largeur de la page, et le conteneur défile d'autant :
 * agrandir par `transform` aurait grossi la page sans agrandir la zone de
 * défilement, et les bords seraient devenus inatteignables au-delà de 100 %.
 */
// Largeur d'une page à 100 %, en pixels : la mesure d'un livre tenu à bout de
// bras, pas celle de l'écran. Au-delà, l'œil perd la ligne en revenant à
// gauche.
const PAGE_WIDTH = 52 * 16;

export function ReaderViewport({
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
  // Le conteneur est tenu en état et non en référence : les pages ont besoin
  // de le désigner comme racine d'observation, et une référence encore vide au
  // premier rendu ne provoquerait aucun second rendu pour la corriger.
  const [scroller, setScroller] = useState<HTMLDivElement | null>(null);
  const [content, setContent] = useState<HTMLDivElement | null>(null);
  // La largeur est calculée ici plutôt que confiée à `calc(min(…) * zoom)` :
  // la référence doit être bornée **avant** d'être multipliée. Écrite
  // `min(100%, 52rem * zoom)`, elle plafonnait à la largeur du conteneur, et
  // le zoom ne faisait plus rien au-delà d'environ 170 % sur un écran large.
  const [available, setAvailable] = useState(PAGE_WIDTH);
  const { report, reported } = useMostVisiblePage(onVisiblePage);

  useEffect(() => {
    // Mesuré sur la zone de contenu et non sur le conteneur : `clientWidth`
    // inclut le rembourrage, et la page dépassait alors de 32 px sur un
    // téléphone — juste assez pour qu'elle ne tienne plus.
    if (!content) return;
    // Une largeur nulle n'est pas une mesure : avant la mise en page, et
    // dans un environnement qui n'en fait aucune, `clientWidth` vaut zéro et
    // la page s'afficherait sans largeur. On garde alors la mesure de
    // référence.
    const measure = () => setAvailable(content.clientWidth || PAGE_WIDTH);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(content);
    return () => observer.disconnect();
  }, [content]);

  // Navigation demandée depuis la barre : on amène la page sous les yeux.
  // Rien à faire si c'est le défilement qui vient de l'annoncer, sinon la vue
  // se recalerait sans cesse sur ce qu'on est déjà en train de lire.
  useEffect(() => {
    if (reported.current === pageNumber) return;
    const target = scroller?.querySelector(`[data-page="${pageNumber}"]`);
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [pageNumber, reported, scroller]);

  return (
    <div
      ref={setScroller}
      // `tabIndex` : sans lui, les flèches et la barre d'espace ne défilent
      // pas tant qu'on n'a pas cliqué dans la page.
      tabIndex={0}
      aria-label="Document"
      className="h-full overflow-y-auto overflow-x-auto bg-[var(--navy-soft)] px-4 py-6 focus-visible:outline-none sm:px-6"
    >
      {/* La largeur de référence est la plus petite entre la page confortable
          et le conteneur — c'est elle qui tient sur un téléphone — et le zoom
          la multiplie. Écrit `min(100%, 52rem * zoom)`, le zoom ne faisait
          plus rien au-delà d'environ 170 % sur un écran large : le plafond
          était atteint avant l'échelle. */}
      <div ref={setContent} className="w-full">
        <div
          className="mx-auto flex flex-col gap-6"
          style={{ width: Math.round(Math.min(available, PAGE_WIDTH) * zoom) }}
        >
          {manifest.items.map((canvas) => (
            <ReaderPageImage
              key={canvasPageNumber(canvas)}
              canvas={canvas}
              sessionKey={sessionKey}
              scroller={scroller}
              onVisible={report}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
