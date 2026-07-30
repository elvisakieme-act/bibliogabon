import type { SearchResult } from "@/api/types";
import { DomainBadge } from "@/components/catalog/DomainBadge";

export function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <article className="rounded-2xl border border-border bg-white p-5 shadow-editorial">
      <a href={`/documents/${result.id}`} className="font-display text-xl leading-tight text-[var(--navy)] hover:text-[var(--green)]">
        {result.title}
      </a>
      <p className="mt-2 text-sm text-muted-foreground">{result.abstract}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        {result.domain ? <DomainBadge domain={result.domain} /> : <span className="font-semibold uppercase tracking-[0.14em] text-[var(--green)]">Domaine non renseigne</span>}
        <span>{result.language_code.toUpperCase()}</span>
        {result.publication_year ? <span>{result.publication_year}</span> : null}
      </div>
    </article>
  );
}
