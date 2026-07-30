import { SiteLayout } from "@/components/layout/SiteLayout";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDomains } from "@/features/catalog/hooks";

export function DomainesPage() {
  const domains = useDomains();
  return <SiteLayout><main className="container-editorial py-10 sm:py-14"><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">Collections</p><h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy)]">Domaines</h1><p className="mt-3 max-w-2xl text-muted-foreground">Explorez les ressources par discipline academique.</p>{domains.isPending ? <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><Skeleton /><Skeleton /><Skeleton /></div> : domains.isError ? <div className="mt-8"><EmptyState title="Domaines indisponibles" description="Reessayez dans quelques instants." /></div> : domains.data?.results.length ? <section className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{domains.data.results.map((domain) => <a key={domain.id} href={`/domaines/${domain.slug}`} className="group rounded-xl border border-border bg-white p-6 shadow-editorial transition hover:-translate-y-0.5 hover:shadow-editorial-lg"><span className="size-2 rounded-full bg-[var(--green)]" aria-hidden="true" /><h2 className="mt-5 font-display text-2xl text-[var(--navy)] group-hover:text-[var(--green)]">{domain.name}</h2><span className="mt-3 inline-block text-sm font-semibold text-muted-foreground">Voir les documents</span></a>)}</section> : <div className="mt-8"><EmptyState title="Aucun domaine" description="Les domaines seront disponibles prochainement." /></div>}</main></SiteLayout>;
}
