import type OpenSeadragon from "openseadragon";
import { useEffect } from "react";
import { createRoot, type Root } from "react-dom/client";

import { ReaderTextLayer } from "@/components/reader/ReaderTextLayer";
import { useReaderPage } from "@/features/reader/hooks";
import { canvasPageNumber, type IiifManifest } from "@/features/reader/manifest";

/**
 * La couche texte, posée sur les pages du visualiseur.
 *
 * C'est la raison pour laquelle le visualiseur reste le nôtre. Universal
 * Viewer n'affiche pas le texte OCR nativement — c'est un greffon d'un fork —
 * et l'étude d'accessibilité du CRKN sur Mirador 3 recense douze défauts
 * majeurs sans aborder la sélection de texte. Cette couche rend la page
 * sélectionnable selon l'accord de droits, cherchable, et lisible par un
 * lecteur d'écran.
 *
 * Les positions sont exprimées en fractions de la page, et OpenSeadragon
 * place un recouvrement en coordonnées du monde : les deux se correspondent
 * directement, et la couche suit donc le zoom et le déplacement sans aucun
 * calcul de notre part.
 *
 * Seules les pages autour de celle qu'on lit reçoivent leur couche. Les
 * demander toutes ferait une requête par page à l'ouverture — et, chaque page
 * demandée étant journalisée, enregistrerait le document entier comme lu.
 */
const NEIGHBOURHOOD = 1;

export function ReaderTextOverlays({
  viewer,
  manifest,
  sessionKey,
  pageNumber
}: {
  viewer: OpenSeadragon.Viewer | null;
  manifest: IiifManifest;
  sessionKey: string;
  pageNumber: number;
}) {
  const wanted = manifest.items
    .map((canvas, index) => ({ page: canvasPageNumber(canvas), index }))
    .filter(({ page }) => Math.abs(page - pageNumber) <= NEIGHBOURHOOD);

  return (
    <>
      {wanted.map(({ page, index }) => (
        <PageTextOverlay
          key={page}
          viewer={viewer}
          sessionKey={sessionKey}
          pageNumber={page}
          itemIndex={index}
        />
      ))}
    </>
  );
}

function PageTextOverlay({
  viewer,
  sessionKey,
  pageNumber,
  itemIndex
}: {
  viewer: OpenSeadragon.Viewer | null;
  sessionKey: string;
  pageNumber: number;
  itemIndex: number;
}) {
  const page = useReaderPage(sessionKey, pageNumber, Boolean(viewer));

  useEffect(() => {
    const data = page.data;
    if (!viewer || !data || data.words.length === 0) return;
    const item = viewer.world.getItemAt(itemIndex);
    if (!item) return;

    const element = document.createElement("div");
    element.style.position = "relative";
    const root: Root = createRoot(element);
    root.render(<ReaderTextLayer words={data.words} policy={data.text_policy} />);

    viewer.addOverlay({ element, location: item.getBounds() });

    return () => {
      viewer.removeOverlay(element);
      // Différé : démonter une racine React pendant le rendu de son parent
      // déclenche un avertissement et laisse l'élément à moitié détaché.
      queueMicrotask(() => root.unmount());
    };
  }, [viewer, page.data, itemIndex]);

  return null;
}
