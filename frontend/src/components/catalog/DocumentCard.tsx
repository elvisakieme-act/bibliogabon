import { Heart } from "lucide-react";

import type { DocumentMetadata } from "@/api/types";
import { DocumentCover } from "@/components/catalog/DocumentCover";
import { documentReadLabel } from "@/components/catalog/documentLabels";
import { DomainBadge } from "@/components/catalog/DomainBadge";

interface FavoriteControl {
  isFavorite: boolean;
  isPending?: boolean;
  onToggle(): void;
}

export function DocumentCard({
  document,
  favorite
}: {
  document: DocumentMetadata;
  favorite?: FavoriteControl;
}) {
  const readLabel = documentReadLabel(document);
  const authors = document.authors.map((author) => author.display_name).join(", ");

  return (
    <article className="group overflow-hidden rounded-2xl border border-border bg-white shadow-editorial transition hover:-translate-y-0.5 hover:shadow-editorial-lg">
      <div className="h-1 gabon-stripe" aria-hidden="true" />
      <DocumentCover document={document} />
      <div className="p-5">
        {document.domain ? <DomainBadge domain={document.domain} /> : null}
        <div className="mt-3 flex items-start gap-3">
          <a
            href={`/documents/${document.id}`}
            className="min-w-0 flex-1 font-display text-xl leading-tight text-[var(--navy)] hover:text-[var(--green)]"
          >
            {document.title}
          </a>
          {favorite ? (
            <button
              type="button"
              aria-label={favorite.isFavorite ? "Retirer des favoris" : "Ajouter aux favoris"}
              aria-pressed={favorite.isFavorite}
              disabled={favorite.isPending}
              onClick={favorite.onToggle}
              className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg border border-border text-[var(--navy)] transition hover:bg-[var(--navy-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] disabled:opacity-60"
            >
              <Heart className="size-5" fill={favorite.isFavorite ? "currentColor" : "none"} />
            </button>
          ) : null}
        </div>
        {authors ? <p className="mt-2 text-sm text-[var(--ink)]">{authors}</p> : null}
        <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{document.abstract}</p>
        {/* La nature du document ouvre la ligne : un cours, une thèse et un
            sujet d'examen ne se lisent pas pour les mêmes raisons, et c'est
            souvent elle qui décide qu'on ouvre ou non. La langue ne s'affiche
            que lorsqu'elle sort de l'ordinaire : « FR » sur chaque carte d'une
            bibliothèque francophone n'apprend rien et occupe la place de ce
            qui en vaudrait la peine. */}
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {document.document_type ? (
            <span className="font-semibold text-[var(--navy)]">
              {document.document_type.name}
            </span>
          ) : null}
          {document.publication_year ? <span>{document.publication_year}</span> : null}
          {document.page_count ? (
            <span>
              {document.page_count} page{document.page_count > 1 ? "s" : ""}
            </span>
          ) : null}
          {document.language_code !== "fr" ? (
            <span className="uppercase">{document.language_code}</span>
          ) : null}
        </div>
        {document.access.can_read ? (
          <a
            href={`/lecture/${document.id}`}
            className="mt-4 inline-flex border-b-2 border-[var(--gold)] pb-1 text-sm font-semibold text-[var(--navy)] hover:text-[var(--green)]"
          >
            {readLabel}
          </a>
        ) : (
          <span className="mt-4 inline-flex text-sm font-semibold text-muted-foreground">
            {readLabel}
          </span>
        )}
      </div>
    </article>
  );
}
