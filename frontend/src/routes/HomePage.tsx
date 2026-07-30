import { DocumentCard } from "@/components/catalog/DocumentCard";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocuments, useDomains } from "@/features/catalog/hooks";

export function HomePage() {
  const featured = useDocuments({ page_size: 4 });
  const domains = useDomains();

  return (
    <SiteLayout>
      <main>
        <section className="relative overflow-hidden border-b border-border bg-[var(--navy)] text-white">
          <div className="h-1 gabon-stripe" aria-hidden="true" />
          <div className="container-editorial py-20">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--gold)]">Bibliotheque academique nationale</p>
            <h1 className="mt-4 max-w-3xl font-display text-5xl font-semibold leading-tight">BiblioGABON</h1>
            <p className="mt-5 max-w-2xl text-white/80">Decouvrez, recherchez et lisez les ressources academiques du Gabon.</p>
            <form action="/recherche" className="mt-8 flex max-w-2xl gap-2 rounded-xl bg-white p-2 shadow-editorial"><label className="sr-only" htmlFor="home-search">Rechercher dans le catalogue</label><input id="home-search" name="q" placeholder="Titre, auteur ou domaine" className="min-w-0 flex-1 rounded-lg px-3 py-2 text-[var(--navy)] outline-none" /><button className="rounded-lg bg-[var(--green)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--navy)]">Rechercher</button></form>
          </div>
        </section>
        <section className="container-editorial py-12"><div className="flex items-end justify-between gap-4"><div><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">Disciplines</p><h2 className="mt-2 font-display text-3xl text-[var(--navy)]">Explorer par domaine</h2></div><a href="/domaines" className="text-sm font-semibold text-[var(--navy)] hover:text-[var(--green)]">Tous les domaines</a></div><div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{domains.data?.results.slice(0, 4).map((domain) => <a key={domain.id} href={`/domaines/${domain.slug}`} className="rounded-xl border border-border bg-[var(--surface-alt)] p-5 font-display text-xl text-[var(--navy)] hover:text-[var(--green)]">{domain.name}</a>)}</div></section>
        <section className="border-t border-border bg-[var(--surface-alt)]"><div className="container-editorial py-12"><div className="flex items-end justify-between gap-4"><div><p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">Selection</p><h2 className="mt-2 font-display text-3xl text-[var(--navy)]">Documents a la une</h2></div><a href="/catalogue" className="text-sm font-semibold text-[var(--navy)] hover:text-[var(--green)]">Voir le catalogue</a></div>{featured.isPending ? <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4"><Skeleton /><Skeleton /><Skeleton /><Skeleton /></div> : featured.data?.results.length ? <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">{featured.data.results.map((document) => <DocumentCard key={document.id} document={document} />)}</div> : <p className="mt-6 text-muted-foreground">Les documents a la une seront disponibles prochainement.</p>}</div></section>
      </main>
    </SiteLayout>
  );
}
