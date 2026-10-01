import { useEffect, useRef, useState } from "react";

import { ReaderTextLayer } from "@/components/reader/ReaderTextLayer";
import { useReaderPage, useReaderPageImage } from "@/features/reader/hooks";
import { canvasPageNumber, type IiifCanvas } from "@/features/reader/manifest";

/**
 * La surface d'une page : son image, et le texte par-dessus.
 *
 * Partagée par les deux sens de lecture. Ce qui les distingue — quand charger,
 * comment disposer — reste chez eux : c'est précisément en faisant partager
 * *le mécanisme* à trois modes qu'aucun des trois ne fonctionnait.
 *
 * La page mesure sa propre largeur plutôt que de la recevoir calculée. Une
 * seconde écriture de la formule finirait par diverger, et surtout un
 * téléphone demanderait l'image dimensionnée pour un écran large : la
 * connexion qu'on voulait ménager paierait le zoom de quelqu'un d'autre.
 */
export function ReaderPageSurface({
  canvas,
  sessionKey,
  enabled
}: {
  canvas: IiifCanvas;
  sessionKey: string;
  enabled: boolean;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const pageNumber = canvasPageNumber(canvas);
  const page = useReaderPage(sessionKey, pageNumber, enabled);
  const service = canvas.items[0].items[0].body.service[0];

  useEffect(() => {
    const element = holder.current;
    if (!element) return;
    const measure = () => setWidth(element.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // La taille demandée est la plus petite que le serveur annonce et qui
  // couvre encore la largeur affichée, densité d'écran comprise. En demander
  // une plus grande ferait payer au lecteur des pixels qu'il ne verra pas ;
  // une plus petite donnerait un texte flou.
  const wanted = width * (typeof window === "undefined" ? 1 : window.devicePixelRatio || 1);
  const size =
    [...service.sizes].sort((a, b) => a.width - b.width).find((s) => s.width >= wanted) ??
    service.sizes[0];

  // Rien n'est demandé tant que la largeur n'est pas connue : une requête
  // partie à zéro ramènerait la plus petite taille, et la page resterait
  // floue jusqu'au premier redimensionnement.
  const ready = enabled && width > 0;
  const path = ready
    ? new URL(`${service.id}/full/${size.width},${size.height}/0/default.webp`).pathname
    : null;
  const image = useReaderPageImage(path, ready);
  const [source, setSource] = useState<string | null>(null);

  useEffect(() => {
    if (!image.data) {
      setSource(null);
      return;
    }
    // Créée ici et révoquée à la sortie : une adresse `blob:` mise en cache
    // survivrait à sa révocation, et la page reviendrait vide.
    const url = URL.createObjectURL(image.data);
    setSource(url);
    return () => {
      URL.revokeObjectURL(url);
      setSource(null);
    };
  }, [image.data]);

  return (
    <div ref={holder} data-page={pageNumber} className="relative h-full w-full bg-white">
      {source ? (
        <>
          <img src={source} alt="" className="block h-full w-full" />
          {page.data ? (
            <ReaderTextLayer words={page.data.words} policy={page.data.text_policy} />
          ) : null}
        </>
      ) : (
        <div className="flex h-full items-center justify-center" role="status">
          <span className="text-sm text-[var(--muted-foreground)]">
            {image.isError ? "Cette page n'a pas pu être affichée." : `Page ${pageNumber}`}
          </span>
        </div>
      )}
      <span className="sr-only">Page {pageNumber}</span>
    </div>
  );
}
