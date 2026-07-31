import { useLocation } from "@tanstack/react-router";

import { CatalogFilters } from "@/components/catalog/CatalogFilters";
import { PaginationControls } from "@/components/catalog/PaginationControls";
import { SearchResultCard } from "@/components/catalog/SearchResultCard";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDomains, useSearch } from "@/features/catalog/hooks";
import { paginationFromSearch } from "@/routes/paginationParams";

function searchValues(searchStr: string) {
  const values = Object.fromEntries(new URLSearchParams(searchStr));
  return { q: values.q, domain: values.domain, language: values.language, access: values.access, year: values.year };
}

export function RecherchePage() {
  const location = useLocation();
  const values = searchValues(location.searchStr);
  const { page, pageSize } = paginationFromSearch(location.searchStr);
  const search = useSearch({ ...values, page, page_size: pageSize });
  const domains = useDomains();

  return <SiteLayout><main className="container-editorial py-10 sm:py-14"><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">Decouverte</p><h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy)]">Recherche</h1><div className="mt-8"><CatalogFilters values={values} domains={domains.data?.results} /></div>{search.isPending ? <div className="mt-8 space-y-4"><Skeleton /><Skeleton /><Skeleton /></div> : search.isError ? <div className="mt-8"><EmptyState title="Recherche indisponible" description="Reessayez dans quelques instants." /></div> : search.data?.results.length ? <><section className="mt-8 space-y-4">{search.data.results.map((result) => <SearchResultCard key={result.id} result={result} />)}</section><PaginationControls response={search.data} page={page} pageSize={pageSize} path="/recherche" params={values} /></> : <div className="mt-8"><EmptyState title="Aucun resultat" description="Essayez avec une autre recherche ou un filtre plus large." /></div>}</main></SiteLayout>;
}
