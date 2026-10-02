import { useEffect, useState } from "react";

import { usePagePreload } from "@/components/reader/usePagePreload";
import { useReaderPageImage } from "@/features/reader/hooks";
import {
  canvasPageNumber,
  type IiifCanvas,
  type IiifManifest
} from "@/features/reader/manifest";

/**
 * Le volet des pages : se repérer dans un long document.
 *
 * Les flèches et le numéro de page suffisent à trois pages, pas à cent
 * cinquante-sept. On y voit la forme des pages — un chapitre qui commence, un
 * tableau, une planche — et c'est ainsi qu'on retrouve un passage dont on ne
 * sait plus le numéro.
 *
 * Les vignettes passent par un point d'entrée qui vérifie le droit comme
 * l'image de page mais **n'écrit pas au journal d'accès** : ouvrir ce volet
 * sur un cours de 157 pages y inscrirait sinon 157 pages lues, et les rapports
 * d'usage institutionnels compteraient des pages que personne n'a lues. Se
 * repérer n'est pas lire — arbitrage posé avec le porteur du produit.
 *
 * Et elles ne sont demandées qu'à l'approche du volet : les charger toutes
 * inonderait la connexion que ce lecteur est censé ménager.
 */
export function ReaderThumbnailPanel({
  open,
  sessionKey,
  manifest,
  pageNumber,
  onSelect,
  onClose
}: {
  open: boolean;
  sessionKey: string;
  manifest: IiifManifest;
  pageNumber: number;
  onSelect(pageNumber: number): void;
  onClose(): void;
}) {
  const [scroller, setScroller] = useState<HTMLDivElement | null>(null);

  // La page courante est amenée sous les yeux à l'ouverture : sur 157 pages,
  // un volet qui s'ouvre au début oblige à retrouver où l'on en était.
  useEffect(() => {
    if (!open || !scroller) return;
    scroller
      .querySelector(`[data-thumbnail="${pageNumber}"]`)
      ?.scrollIntoView({ block: "center" });
    // `pageNumber` volontairement absent : on recale à l'ouverture, pas à
    // chaque page tournée pendant que le volet est ouvert.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, scroller]);

  if (!open) return null;

  return (
    <>
      {/* Le voile ferme au clic et assombrit la lecture : sur un téléphone, le
          volet couvre la page, et rien ne dirait sinon comment en sortir. */}
      <button
        type="button"
        aria-label="Fermer le volet des pages"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-[var(--navy-deep)]/40 md:hidden"
      />
      <aside
        aria-label="Pages du document"
        className="absolute inset-y-0 start-0 z-40 flex w-56 flex-col border-e border-white/10 bg-[var(--navy-deep)] sm:w-64"
      >
        <div className="flex items-center justify-between px-4 py-3 text-white/80">
          <span className="text-sm font-semibold">Pages</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer le volet des pages"
            className="rounded-lg px-2 py-1 text-lg leading-none transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
          >
            <span aria-hidden>×</span>
          </button>
        </div>
        <div ref={setScroller} className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          <ol className="space-y-3">
            {manifest.items.map((canvas) => (
              <Vignette
                key={canvasPageNumber(canvas)}
                canvas={canvas}
                sessionKey={sessionKey}
                scroller={scroller}
                current={canvasPageNumber(canvas) === pageNumber}
                onSelect={onSelect}
              />
            ))}
          </ol>
        </div>
      </aside>
    </>
  );
}

function Vignette({
  canvas,
  sessionKey,
  scroller,
  current,
  onSelect
}: {
  canvas: IiifCanvas;
  sessionKey: string;
  scroller: Element | null;
  current: boolean;
  onSelect(pageNumber: number): void;
}) {
  const pageNumber = canvasPageNumber(canvas);
  const { holder, approaching } = usePagePreload<HTMLButtonElement>({
    root: scroller,
    margin: "600px 0px"
  });
  const image = useReaderPageImage(
    `/api/v1/reader/sessions/${sessionKey}/pages/${pageNumber}/thumbnail/`,
    approaching
  );
  const [source, setSource] = useState<string | null>(null);

  useEffect(() => {
    if (!image.data) {
      setSource(null);
      return;
    }
    // Créée ici et révoquée à la sortie : une adresse `blob:` mise en cache
    // survivrait à sa révocation, et la vignette reviendrait vide.
    const url = URL.createObjectURL(image.data);
    setSource(url);
    return () => {
      URL.revokeObjectURL(url);
      setSource(null);
    };
  }, [image.data]);

  return (
    <li data-thumbnail={pageNumber}>
      <button
        ref={holder}
        type="button"
        onClick={() => onSelect(pageNumber)}
        aria-current={current ? "page" : undefined}
        className="block w-full text-start focus-visible:outline-none"
      >
        <span
          className={`block overflow-hidden rounded border-2 bg-white/5 transition ${
            current ? "border-[var(--gold)]" : "border-transparent hover:border-white/40"
          }`}
          style={{ aspectRatio: `${canvas.width} / ${canvas.height}` }}
        >
          {source ? (
            <img src={source} alt="" loading="lazy" className="h-full w-full object-cover" />
          ) : null}
        </span>
        <span
          className={`mt-1 block text-xs ${current ? "font-semibold text-[var(--gold)]" : "text-white/60"}`}
        >
          Page {pageNumber}
        </span>
      </button>
    </li>
  );
}
