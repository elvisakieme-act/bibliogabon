import { useEffect, useRef, useState } from "react";

import { ReaderTextLayer } from "@/components/reader/ReaderTextLayer";
import { useReaderPage, useReaderPageImage } from "@/features/reader/hooks";
import { canvasPageNumber, type IiifCanvas } from "@/features/reader/manifest";

/**
 * Une page du document, dans un défilement ordinaire.
 *
 * La page réserve sa place avant d'arriver : le cadre tient le rapport donné
 * par le manifeste, donc rien ne saute sous les yeux du lecteur quand l'image
 * se charge. Sans cette réserve, chaque page arrivée décalerait ce qu'on est
 * en train de lire.
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
  // La page mesure sa propre largeur plutôt que de la recevoir calculée :
  // une seconde écriture de la formule finirait par diverger, et surtout un
  // téléphone demanderait l'image dimensionnée pour un écran large — la
  // connexion qu'on voulait ménager paierait le zoom de quelqu'un d'autre.
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const element = holder.current;
    if (!element) return;
    const measure = () => setWidth(element.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const pageNumber = canvasPageNumber(canvas);
  const page = useReaderPage(sessionKey, pageNumber, approaching);
  const service = canvas.items[0].items[0].body.service[0];

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
  const path =
    approaching && width > 0
      ? new URL(`${service.id}/full/${size.width},${size.height}/0/default.webp`).pathname
      : null;
  const image = useReaderPageImage(path, approaching && width > 0);
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
      data-page={pageNumber}
      className="relative bg-white shadow-editorial"
      style={{ aspectRatio: `${canvas.width} / ${canvas.height}` }}
    >
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
