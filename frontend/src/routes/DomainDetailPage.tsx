import { useLocation, useParams } from "@tanstack/react-router";

import { PaginationControls } from "@/components/catalog/PaginationControls";
import { SearchResultCard } from "@/components/catalog/SearchResultCard";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDomains, useSearch } from "@/features/catalog/hooks";

export function DomainDetailPage() {
  const { slug } = useParams({ from: "/domaines/$slug" });
  const location = useLocation();
  const page = Number(new URLSearchParams(location.searchStr).get("page") ?? 1) || 1;
  const pageSize = Number(new URLSearchParams(location.searchStr).get("page_size") ?? 12) || 12;
  const search = useSearch({ domain: slug, page, page_size: pageSize });
  const domains = useDomains();
  const name = domains.data?.results.find((domain) => domain.slug === slug)?.name ?? slug;

  return <SiteLayout><main className="container-editorial py-10 sm:py-14"><a href="/domaines" className="text-sm font-semibold text-[var(--green)] hover:underline">Domaines</a><h1 className="mt-3 font-display text-4xl font-semibold capitalize text-[var(--navy)]">{name}</h1>{search.isPending ? <div className="mt-8 space-y-4"><Skeleton /><Skeleton /><Skeleton /></div> : search.isError ? <div className="mt-8"><EmptyState title="Domaine indisponible" description="Reessayez dans quelques instants." /></div> : search.data?.results.length ? <><section className="mt-8 space-y-4">{search.data.results.map((result) => <SearchResultCard key={result.id} result={result} />)}</section><PaginationControls response={search.data} page={page} pageSize={pageSize} path={`/domaines/${slug}`} params={{ domain: slug }} /></> : <div className="mt-8"><EmptyState title="Aucun document" description="Aucun document ne correspond encore a ce domaine." /></div>}</main></SiteLayout>;
}
