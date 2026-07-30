import { SiteLayout } from "@/components/layout/SiteLayout";

export function LecturePage() {
  return (
    <SiteLayout>
      <main className="container-editorial py-10 sm:py-16">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--green)]">BiblioGABON</p>
        <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy)]">Lecture</h1>
      </main>
    </SiteLayout>
  );
}
