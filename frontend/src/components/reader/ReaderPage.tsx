import { useEffect, useState } from "react";

import type { ReaderPage as ReaderPagePayload } from "@/api/types";
import { ReaderTextLayer } from "@/components/reader/ReaderTextLayer";
import { reflowExtractedText } from "@/components/reader/reflowExtractedText";
import { useReaderPageImage } from "@/features/reader/hooks";

interface ReaderPageProps {
  title: string;
  page: ReaderPagePayload;
}

export function ReaderPage({ title, page }: ReaderPageProps) {
  // Plus d'en-tête ici : la barre du lecteur porte le titre, et le répéter à
  // chaque page le ferait relire à un lecteur d'écran autant de fois qu'il y
  // a de pages. Le titre reste utilisé pour la légende accessible.
  return (
    <article
      className="bg-white shadow-editorial"
      aria-label={`${title} — page ${page.page_number}`}
    >
      {page.image ? (
        <PageImage page={page} />
      ) : (
        <div className="px-6 py-8 sm:px-10 sm:py-12">
          <FlatText text={page.text} pageNumber={page.page_number} />
        </div>
      )}
    </article>
  );
}

/**
 * La page telle qu'elle a été mise en page, avec sa couche texte.
 *
 * Le cadre garde le format d'une page **avant** que l'image arrive. Sans
 * cela, une image absente ou refusée laissait l'article sans hauteur : le
 * lecteur affichait un vide, et rien ne disait pourquoi.
 *
 * L'image porte `alt=""` : le texte qui la décrit est juste au-dessus, dans
 * la couche transparente, et une alternative le répéterait à chaque page.
 */
function PageImage({ page }: { page: ReaderPagePayload }) {
  const image = useReaderPageImage(page.image);
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
    <figure className="relative aspect-[1/1.414] w-full bg-white">
      {source ? (
        <>
          <img src={source} alt="" className="absolute inset-0 h-full w-full object-contain" />
          <ReaderTextLayer words={page.words} policy={page.text_policy} />
        </>
      ) : (
        <div className="absolute inset-0 flex items-center justify-center" role="status">
          <span className="text-sm text-[var(--muted-foreground)]">
            {image.isError
              ? "Cette page n'a pas pu être affichée."
              : `Page ${page.page_number}`}
          </span>
        </div>
      )}
      <figcaption className="sr-only">
        Page {page.page_number} sur {page.page_count}
      </figcaption>
    </figure>
  );
}

/**
 * Repli quand la page n'a pas de rendu.
 *
 * Le texte n'est plus affiché tel quel : les retours à la ligne d'un PDF sont
 * ceux de sa mise en page, pas ceux du propos. Les conserver faisait replier
 * le texte deux fois sur téléphone — au gabarit du document puis à l'écran —
 * et le rendait illisible.
 */
function FlatText({ text, pageNumber }: { text: string; pageNumber: number }) {
  const paragraphs = reflowExtractedText(text, pageNumber);
  return (
    <div className="mx-auto max-w-2xl font-display text-lg leading-8 text-[var(--navy)] sm:text-xl sm:leading-9">
      {paragraphs.map((paragraph, index) => (
        <p key={index} className={index > 0 ? "mt-5" : undefined}>
          {paragraph}
        </p>
      ))}
    </div>
  );
}
