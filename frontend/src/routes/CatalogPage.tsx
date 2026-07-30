import { CatalogFilters } from "@/components/catalog/CatalogFilters";
import { DocumentCard } from "@/components/catalog/DocumentCard";
import { PaginationControls } from "@/components/catalog/PaginationControls";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocuments, useDomains } from "@/features/catalog/hooks";

export function CatalogPage() {
  const page = Number(new URLSearchParams(window.location.search).get("page") ?? 1) || 1;
  const pageSize = Number(new URLSearchParams(window.location.search).get("page_size") ?? 12) || 12;
  const documents = useDocuments({ page, page_size: pageSize });
  const domains = useDomains();

  return <SiteLayout><main className="container-editorial py-10 sm:py-14"><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">Explorer</p><h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy)]">Catalogue</h1><p className="mt-3 max-w-2xl text-muted-foreground">Parcourez les publications academiques accessibles sur BiblioGABON.</p><div className="mt-8"><CatalogFilters values={{}} domains={domains.data?.results} /></div>{documents.isPending ? <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3"><Skeleton /><Skeleton /><Skeleton /></div> : documents.isError ? <div className="mt-8"><EmptyState title="Catalogue indisponible" description="Reessayez dans quelques instants." /></div> : documents.data?.results.length ? <><section className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{documents.data.results.map((document) => <DocumentCard key={document.id} document={document} />)}</section><PaginationControls response={documents.data} page={page} pageSize={pageSize} path="/catalogue" /></> : <div className="mt-8"><EmptyState title="Aucun document" description="Le catalogue ne contient pas encore de document public." /></div>}</main></SiteLayout>;
}
