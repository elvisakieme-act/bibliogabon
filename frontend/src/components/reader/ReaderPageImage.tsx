import { useEffect, useRef, useState } from "react";

import { ReaderPageSurface } from "@/components/reader/ReaderPageSurface";
import { canvasPageNumber, type IiifCanvas } from "@/features/reader/manifest";

/**
 * Une page dans le défilement.
 *
 * Elle réserve sa place avant d'arriver : le cadre tient le rapport donné par
 * le manifeste, donc rien ne saute sous les yeux du lecteur quand l'image se
 * charge. Sans cette réserve, chaque page arrivée décalerait ce qu'on est en
 * train de lire.
 *
 * L'image n'est demandée qu'à l'approche de l'écran. Les charger toutes
 * inonderait la connexion — et le journal d'accès, qui enregistrerait les 157
 * pages d'un cours comme lues avant que le lecteur en ait tourné une.
 */
export function ReaderPageImage({
  canvas,
  sessionKey,
  onVisible
}: {
  canvas: IiifCanvas;
  sessionKey: string;
  onVisible(pageNumber: number, ratio: number): void;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const [approaching, setApproaching] = useState(false);
  const pageNumber = canvasPageNumber(canvas);

  useEffect(() => {
    const element = holder.current;
    if (!element) return;

    // Deux observateurs, deux seuils. Un large pour charger d'avance —
    // charger au moment où la page entre à l'écran la ferait apparaître vide.
    // Un échelonné pour savoir laquelle est réellement lue.
    const preload = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setApproaching(true);
          preload.disconnect();
        }
      },
      { rootMargin: "1400px 0px" }
    );
    preload.observe(element);

    const current = new IntersectionObserver(
      ([entry]) => onVisible(pageNumber, entry.isIntersecting ? entry.intersectionRatio : 0),
      { threshold: [0, 0.1, 0.25, 0.5, 0.75, 1] }
    );
    current.observe(element);

    return () => {
      preload.disconnect();
      current.disconnect();
    };
  }, [onVisible, pageNumber]);

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
