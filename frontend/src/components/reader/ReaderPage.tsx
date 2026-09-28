import type { ReaderPage as ReaderPagePayload } from "@/api/types";
import { ReaderTextLayer } from "@/components/reader/ReaderTextLayer";
import { reflowExtractedText } from "@/components/reader/reflowExtractedText";

interface ReaderPageProps {
  title: string;
  page: ReaderPagePayload;
}

export function ReaderPage({ title, page }: ReaderPageProps) {
  return (
    <article className="border border-border bg-white px-6 py-8 shadow-editorial sm:px-10 sm:py-12">
      <header className="border-b border-border pb-5">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">
          Lecture
        </p>
        <h1 className="mt-2 font-display text-3xl font-semibold text-[var(--navy)] sm:text-4xl">
          {title}
        </h1>
      </header>
      <div className="pt-8">
        {page.image ? (
          <PageImage page={page} />
        ) : (
          <FlatText text={page.text} pageNumber={page.page_number} />
        )}
      </div>
    </article>
  );
}

/**
 * La page telle qu'elle a été mise en page, avec sa couche texte.
 *
 * L'image porte `alt=""` : le texte qui la décrit est juste au-dessus, dans la
 * couche transparente, et une alternative le répéterait à chaque page pour un
 * lecteur d'écran.
 */
function PageImage({ page }: { page: ReaderPagePayload }) {
  return (
    <figure className="relative mx-auto max-w-3xl">
      <img
        src={page.image ?? undefined}
        alt=""
        className="w-full border border-[var(--border)] bg-white shadow-sm"
      />
      <ReaderTextLayer words={page.words} />
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
