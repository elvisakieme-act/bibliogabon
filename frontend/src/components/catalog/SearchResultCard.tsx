import type { SearchResult } from "@/api/types";
import { DocumentCover } from "@/components/catalog/DocumentCover";
import { DomainBadge } from "@/components/catalog/DomainBadge";
import { matchedOnlyInText, searchMatchLabel } from "@/components/catalog/searchMatch";

/**
 * Un résultat de recherche, et la raison de sa présence.
 *
 * Le serveur note un titre qui correspond mille fois plus haut qu'un mot
 * croisé au fil d'une page — mais les deux s'affichaient de la même façon, si
 * bien qu'une recherche sur « droit » semblait ramener tout le catalogue.
 * Chaque ligne dit donc d'où vient sa correspondance, et celle qui ne tient
 * qu'au texte du document le dit en premier, car c'est la plus faible.
 */
export function SearchResultCard({ result }: { result: SearchResult }) {
  const provenance = searchMatchLabel(result.matched_in);
  const faible = matchedOnlyInText(result.matched_in);
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
          {result.domain ? <DomainBadge domain={result.domain} /> : null}
          {/* La nature du document — cours, thèse, mémoire — était absente de
              la liste alors qu'elle décide souvent qu'on ouvre ou non. */}
          {result.document_type ? <span>{result.document_type.name}</span> : null}
          {result.publication_year ? <span>{result.publication_year}</span> : null}
          {result.indexed_page_count > 0 ? (
            <span>
              {result.indexed_page_count} page{result.indexed_page_count > 1 ? "s" : ""}
            </span>
          ) : null}
        </div>
        {provenance ? (
          <p
            className={`mt-3 text-xs ${
              faible ? "text-[var(--muted-foreground)]" : "font-semibold text-[var(--green)]"
            }`}
          >
            {provenance}
          </p>
        ) : null}
      </div>
    </article>
  );
}
