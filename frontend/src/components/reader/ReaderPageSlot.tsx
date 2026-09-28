import { useEffect, useRef, useState } from "react";

import { ReaderPage } from "@/components/reader/ReaderPage";
import { useReaderPage } from "@/features/reader/hooks";

/**
 * Emplacement d'une page, chargé à l'approche de l'écran.
 *
 * En défilement continu, demander les 157 pages d'un cours à l'ouverture
 * inonderait le serveur, la connexion du lecteur — et le journal d'accès, qui
 * enregistrerait 157 lectures pour une page réellement lue.
 *
 * L'emplacement réserve sa place avant d'être chargé, au format d'une page A4.
 * Sans cela, chaque page arrivée décalerait ce que le lecteur est en train de
 * lire.
 */
export function ReaderPageSlot({
  sessionKey,
  pageNumber,
  title,
  onVisible
}: {
  sessionKey: string | null;
  pageNumber: number;
  title: string;
  onVisible?: (pageNumber: number, ratio: number) => void;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const [approaching, setApproaching] = useState(false);
  const page = useReaderPage(sessionKey, pageNumber, approaching);

  useEffect(() => {
    const element = holder.current;
    if (!element) return;

    // Deux seuils : un large pour charger d'avance, un étroit pour savoir
    // quelle page est réellement lue. Charger au moment où la page entre à
    // l'écran la ferait apparaître vide.
    const preload = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setApproaching(true);
          preload.disconnect();
        }
      },
      { rootMargin: "1200px 0px" }
    );
    preload.observe(element);

    // Une échelle de seuils, pas un seuil unique : la page courante est la
    // plus visible, ce qui demande de connaître la part visible de chacune et
    // non un simple « elle intersecte ».
    const current = new IntersectionObserver(
      ([entry]) => onVisible?.(pageNumber, entry.isIntersecting ? entry.intersectionRatio : 0),
      { threshold: [0, 0.1, 0.25, 0.5, 0.75, 1] }
    );
    current.observe(element);

    return () => {
      preload.disconnect();
      current.disconnect();
    };
  }, [onVisible, pageNumber]);

  return (
    <div ref={holder} data-page={pageNumber} className="w-full">
      {page.data ? (
        <ReaderPage title={title} page={page.data} />
      ) : (
        <div
          className="flex aspect-[1/1.414] w-full items-center justify-center border border-[var(--border)] bg-white/70"
          role="status"
        >
          <span className="text-sm text-[var(--muted-foreground)]">
            {page.isError ? "Page indisponible" : `Page ${pageNumber}`}
          </span>
        </div>
      )}
    </div>
  );
}
