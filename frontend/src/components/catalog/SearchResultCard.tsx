import type { SearchResult } from "@/api/types";
import { DocumentCover } from "@/components/catalog/DocumentCover";
import { DomainBadge } from "@/components/catalog/DomainBadge";

export function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <article className="flex gap-5 rounded-2xl border border-border bg-white p-5 shadow-editorial">
      {/* La vignette ancre le résultat : une liste de titres sur fond blanc se
          lit comme un index, pas comme une bibliothèque. */}
      <a
        href={`/documents/${result.id}`}
        className="w-20 shrink-0 overflow-hidden rounded-lg sm:w-24"
        tabIndex={-1}
        aria-hidden="true"
      >
        <DocumentCover document={result} />
      </a>
      <div className="min-w-0">
        <a
          href={`/documents/${result.id}`}
          className="font-display text-xl leading-tight text-[var(--navy)] hover:text-[var(--green)]"
        >
          {result.title}
        </a>
        <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">{result.abstract}</p>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          {result.domain ? (
            <DomainBadge domain={result.domain} />
          ) : (
            <span className="font-semibold uppercase tracking-[0.14em] text-[var(--green)]">
              Domaine non renseigné
            </span>
          )}
          <span>{result.language_code.toUpperCase()}</span>
          {result.publication_year ? <span>{result.publication_year}</span> : null}
        </div>
      </div>
    </article>
  );
}
