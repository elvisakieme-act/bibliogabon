import OpenSeadragon from "openseadragon";
import { useEffect, useRef } from "react";

import { useAuth } from "@/auth/useAuth";
import type { ScrollMode } from "@/components/reader/readerPreferences";
import {
  canvasPageNumber,
  canvasTileSource,
  type IiifManifest
} from "@/features/reader/manifest";

/**
 * Le document, affiché par OpenSeadragon.
 *
 * **Un seul visualiseur pour tout le document**, pas un par page. C'est ainsi
 * que fonctionnent Universal Viewer et Mirador, qui reposent sur le même
 * moteur : un composant par page créerait cent cinquante-sept contextes de
 * rendu pour un cours, et le navigateur ne suivrait pas.
 *
 * Les trois sens de lecture sont des dispositions du même monde :
 *
 * - **vertical** — les pages empilées, on fait défiler ;
 * - **horizontal** — les pages en ligne, on glisse de côté ;
 * - **livre** — les pages en ligne aussi, mais la vue se cale sur deux pages
 *   à la fois. La transition est un glissement franc plutôt qu'une animation
 *   de page qui se tourne : le public visé lit en grande partie sur des
 *   téléphones d'entrée de gamme.
 *
 * Le zoom n'est plus un réglage de largeur : le tuilage le rend continu, et
 * c'est le visualiseur qui ne descend que les tuiles regardées.
 */
export function ReaderViewport({
  sessionKey,
  manifest,
  mode,
  pageNumber,
  onVisiblePage,
  onViewerReady
}: {
  sessionKey: string;
  manifest: IiifManifest;
  mode: ScrollMode;
  pageNumber: number;
  onVisiblePage(pageNumber: number): void;
  onViewerReady(viewer: OpenSeadragon.Viewer | null): void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<OpenSeadragon.Viewer | null>(null);
  const { tokens, isHydrating } = useAuth();

  // Les rappels changent à chaque rendu ; les mettre en dépendance de l'effet
  // détruirait et recréerait le visualiseur en boucle, et la lecture
  // repartirait de la première page à chaque fois.
  const visibleRef = useRef(onVisiblePage);
  visibleRef.current = onVisiblePage;
  // Dernière page annoncée par le visualiseur lui-même. Sans elle, annoncer
  // une page déclencherait le recadrage, qui déclencherait une annonce : le
  // lecteur s'ouvrait au milieu du document et ne s'y tenait pas.
  const reportedRef = useRef<number | null>(null);
  const pageRef = useRef(pageNumber);
  pageRef.current = pageNumber;
  const readyRef = useRef(onViewerReady);
  readyRef.current = onViewerReady;

  useEffect(() => {
    if (!host.current || isHydrating) return;

    const viewer = OpenSeadragon({
      element: host.current,
      prefixUrl: "",
      // Converti explicitement : OpenSeadragon accepte un `info.json` IIIF
      // brut à l'exécution, mais ses types ne décrivent que ses propres
      // formats. Le manifeste garantit la forme, et le serveur la produit.
      tileSources: manifest.items.map(canvasTileSource) as unknown as string[],
      // Les tuiles passent par XHR pour porter le jeton : une requête d'image
      // ordinaire n'envoie aucun en-tête, et toutes les pages d'un lecteur
      // connecté reviendraient en 403.
      loadTilesWithAjax: true,
      ajaxHeaders: tokens?.access ? { Authorization: `Bearer ${tokens.access}` } : {},
      crossOriginPolicy: false,
      // Pas `collectionMode` : il dispose les pages dans des cellules
      // carrées, où une page portrait flotte entre deux vides. En mode livre,
      // cela laissait un fossé au milieu de la double page — l'inverse de
      // l'effet recherché. La disposition est donc calculée ici, à partir des
      // dimensions que le manifeste donne.
      showNavigationControl: false,
      showSequenceControl: false,
      gestureSettingsMouse: { clickToZoom: false },
      visibilityRatio: 0.6,
      minZoomImageRatio: 0.4,
      maxZoomPixelRatio: 3,
      animationTime: 0.4,
      springStiffness: 8,
      preserveViewport: true
    });

    viewerRef.current = viewer;
    readyRef.current(viewer);

    // La page lue est celle dont le centre est le plus proche du centre de la
    // vue. Prendre la première qui touche le bord annoncerait la page
    // suivante dès qu'un millimètre en dépasse.
    const reportVisible = () => {
      const centre = viewer.viewport.getCenter();
      let best: number | null = null;
      let bestDistance = Infinity;
      for (let index = 0; index < viewer.world.getItemCount(); index += 1) {
        const bounds = viewer.world.getItemAt(index).getBounds();
        const distance =
          Math.abs(bounds.x + bounds.width / 2 - centre.x) +
          Math.abs(bounds.y + bounds.height / 2 - centre.y);
        if (distance < bestDistance) {
          bestDistance = distance;
          best = index;
        }
      }
      if (best !== null && manifest.items[best]) {
        const page = canvasPageNumber(manifest.items[best]);
        reportedRef.current = page;
        visibleRef.current(page);
      }
    };

    // À l'ouverture, on dispose les pages puis on se place sur celle qui est
    // demandée — la reprise de lecture
    // ou la première page — au lieu de cadrer le document entier, ce qui
    // affichait le milieu.
    viewer.addHandler("open", () => {
      layoutPages(viewer, manifest, mode);
      const index = manifest.items.findIndex(
        (canvas) => canvasPageNumber(canvas) === pageRef.current
      );
      const item = index >= 0 ? viewer.world.getItemAt(index) : null;
      if (item) {
        reportedRef.current = pageRef.current;
        viewer.viewport.fitBounds(item.getBounds(), true);
      }
      reportVisible();
    });
    viewer.addHandler("animation-finish", reportVisible);

    return () => {
      readyRef.current(null);
      viewerRef.current = null;
      viewer.destroy();
    };
    // `pageNumber` est volontairement absent : la navigation déplace la vue,
    // elle ne reconstruit pas le visualiseur.
  }, [manifest, mode, tokens?.access, isHydrating, sessionKey]);

  // Navigation demandée par la barre : on amène la page dans la vue.
  //
  // Rien à faire si le visualiseur vient lui-même d'annoncer cette page :
  // recadrer sur ce qu'on regarde déjà provoquerait un aller-retour sans fin
  // entre l'annonce et le recadrage.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || reportedRef.current === pageNumber) return;
    const index = manifest.items.findIndex((canvas) => canvasPageNumber(canvas) === pageNumber);
    if (index < 0 || index >= viewer.world.getItemCount()) return;

    const bounds = viewer.world.getItemAt(index).getBounds();
    if (mode === "livre" && index > 0) {
      // Deux pages à la fois : on cadre la double, pas la page seule. La
      // couverture (index 0) se présente seule, puis les paires sont (1,2),
      // (3,4)… — donc un index impair s'apparie avec le suivant, un index
      // pair avec le précédent.
      const partner = viewer.world.getItemAt(index % 2 === 1 ? index + 1 : index - 1);
      if (partner) {
        viewer.viewport.fitBounds(bounds.union(partner.getBounds()));
        return;
      }
    }
    viewer.viewport.fitBounds(bounds);
  }, [pageNumber, mode, manifest]);

  return <div ref={host} className="h-full w-full bg-[var(--navy-soft)]" />;
}

// Espace entre deux pages, en fraction de la largeur d'une page. Nul entre
// les deux pages d'une double : c'est ce contact qui fait lire un livre
// plutôt que deux images côte à côte.
const PAGE_GAP = 0.06;
const SPREAD_GAP = 0.24;

/**
 * Place chaque page dans le monde du visualiseur.
 *
 * Toutes les pages sont ramenées à la même largeur — un document mêle souvent
 * des formats, et des pages de largeurs différentes donneraient une colonne
 * en escalier. La hauteur suit le rapport réel de chaque page, lu dans le
 * manifeste : la déduire d'un format supposé déformerait un plan ou un
 * tableau.
 */
function layoutPages(viewer: OpenSeadragon.Viewer, manifest: IiifManifest, mode: ScrollMode) {
  let offset = 0;
  for (let index = 0; index < viewer.world.getItemCount(); index += 1) {
    const item = viewer.world.getItemAt(index);
    const canvas = manifest.items[index];
    if (!item || !canvas) continue;
    const height = canvas.height / canvas.width;

    item.setWidth(1, true);
    if (mode === "vertical") {
      item.setPosition(new OpenSeadragon.Point(0, offset), true);
      offset += height + PAGE_GAP;
    } else if (mode === "horizontal") {
      item.setPosition(new OpenSeadragon.Point(offset, 0), true);
      offset += 1 + PAGE_GAP;
    } else {
      // La première page se présente seule, comme un livre qu'on ouvre ; les
      // suivantes vont par paires, pages paires à gauche — la convention de
      // l'imprimé.
      const isRightHand = index === 0 || index % 2 === 0;
      item.setPosition(new OpenSeadragon.Point(offset, 0), true);
      offset += isRightHand ? 1 + SPREAD_GAP : 1;
    }
  }
}
