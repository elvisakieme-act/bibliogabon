import { useEffect } from "react";

import { ReaderPageSurface } from "@/components/reader/ReaderPageSurface";
import { usePagePreload } from "@/components/reader/usePagePreload";
import { canvasPageNumber, type IiifCanvas } from "@/features/reader/manifest";

/**
 * Une page dans le défilement vertical.
 *
 * Elle réserve sa place avant d'arriver : le cadre tient le rapport donné par
 * le manifeste, donc rien ne saute sous les yeux du lecteur quand l'image se
 * charge. Sans cette réserve, chaque page arrivée décalerait ce qu'on est en
 * train de lire.
 *
 * Elle annonce aussi la part d'elle-même qu'on voit : en défilement vertical,
 * la page lue est la plus visible. La bande horizontale pose la même question
 * autrement — la page la plus centrée — et c'est pourquoi elle ne passe pas
 * par ici.
 */
const THRESHOLDS = [0, 0.1, 0.25, 0.5, 0.75, 1];

export function ReaderPageImage({
  canvas,
  sessionKey,
  scroller,
  onVisible
}: {
  canvas: IiifCanvas;
  sessionKey: string;
  scroller: Element | null;
  onVisible(pageNumber: number, ratio: number): void;
}) {
  const pageNumber = canvasPageNumber(canvas);
  // L'avance se prend en bas : c'est de ce côté que la lecture va.
  const { holder, approaching } = usePagePreload({ root: scroller, margin: "1400px 0px" });

  useEffect(() => {
    const element = holder.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => onVisible(pageNumber, entry.isIntersecting ? entry.intersectionRatio : 0),
      { root: scroller, threshold: THRESHOLDS }
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [holder, onVisible, pageNumber, scroller]);

  return (
    <div
      ref={holder}
      className="shadow-editorial"
      style={{ aspectRatio: `${canvas.width} / ${canvas.height}` }}
    >
      <ReaderPageSurface canvas={canvas} sessionKey={sessionKey} enabled={approaching} />
    </div>
  );
}
