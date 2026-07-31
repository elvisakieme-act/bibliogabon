import { Heart } from "lucide-react";

import type { DocumentMetadata } from "@/api/types";
import { DocumentCover } from "@/components/catalog/DocumentCover";
import { DomainBadge } from "@/components/catalog/DomainBadge";

export function documentReadLabel(document: DocumentMetadata) {
  if (document.access.can_read) return "Lire";
  if (document.access.reason === "authentication_required") return "Connexion requise";
  if (document.access.reason === "entitlement_required") return "Acces requis";
  return "Indisponible";
}

interface FavoriteControl {
  isFavorite: boolean;
  isPending?: boolean;
  onToggle(): void;
}

export function DocumentCard({ document, favorite }: { document: DocumentMetadata; favorite?: FavoriteControl }) {
  const readLabel = documentReadLabel(document);
  const authors = document.authors.map((author) => author.display_name).join(", ");

  return (
    <article className="group overflow-hidden rounded-2xl border border-border bg-white shadow-editorial transition hover:-translate-y-0.5 hover:shadow-editorial-lg">
      <div className="h-1 gabon-stripe" aria-hidden="true" />
      <DocumentCover document={document} />
      <div className="p-5">
        {document.domain ? <DomainBadge domain={document.domain} /> : null}
        <div className="mt-3 flex items-start gap-3">
          <a href={`/documents/${document.id}`} className="min-w-0 flex-1 font-display text-xl leading-tight text-[var(--navy)] hover:text-[var(--green)]">
            {document.title}
          </a>
          {favorite ? <button type="button" aria-label={favorite.isFavorite ? "Retirer des favoris" : "Ajouter aux favoris"} aria-pressed={favorite.isFavorite} disabled={favorite.isPending} onClick={favorite.onToggle} className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg border border-border text-[var(--navy)] transition hover:bg-[var(--navy-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] disabled:opacity-60"><Heart className="size-5" fill={favorite.isFavorite ? "currentColor" : "none"} /></button> : null}
        </div>
        <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">{document.abstract}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
          <span className="rounded-full bg-[var(--navy-soft)] px-2.5 py-1 uppercase">{document.language_code}</span>
          {document.publication_year ? <span>{document.publication_year}</span> : null}
          {authors ? <span>{authors}</span> : null}
        </div>
        {document.access.can_read ? (
          <a href={`/lecture/${document.id}`} className="mt-4 inline-flex border-b-2 border-[var(--gold)] pb-1 text-sm font-semibold text-[var(--navy)] hover:text-[var(--green)]">
            {readLabel}
          </a>
        ) : (
          <span className="mt-4 inline-flex text-sm font-semibold text-muted-foreground">{readLabel}</span>
        )}
      </div>
    </article>
  );
}
