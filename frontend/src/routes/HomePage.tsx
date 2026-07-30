import { SiteLayout } from "@/components/layout/SiteLayout";

export function HomePage() {
  return (
    <SiteLayout>
      <main>
        <section className="relative overflow-hidden border-b border-border bg-[var(--navy)] text-white">
          <div className="h-1 gabon-stripe" aria-hidden="true" />
          <div className="container-editorial py-20">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--gold)]">Bibliotheque academique nationale</p>
            <h1 className="mt-4 max-w-3xl font-display text-5xl font-semibold leading-tight">BiblioGABON</h1>
            <p className="mt-5 max-w-2xl text-white/80">Decouvrez, recherchez et lisez les ressources academiques du Gabon.</p>
          </div>
        </section>
      </main>
    </SiteLayout>
  );
}
