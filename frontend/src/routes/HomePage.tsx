import {
  ArrowRight,
  BookOpen,
  LibraryBig,
  Search,
  ShieldCheck
} from "lucide-react";

import type { DomainSummary } from "@/api/types";
import { DocumentCard } from "@/components/catalog/DocumentCard";
import { SiteLayout } from "@/components/layout/SiteLayout";
import { KenBurnsImage } from "@/components/ui/KenBurnsImage";
import { Reveal } from "@/components/ui/Reveal";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocuments, useDomains } from "@/features/catalog/hooks";

const DOMAIN_TONES = [
  "bg-[var(--navy)] text-white sm:col-span-2 sm:row-span-2",
  "bg-[var(--green-soft)] text-[var(--navy)]",
  "bg-[var(--gold-soft)] text-[var(--navy)]",
  "bg-white text-[var(--navy)]",
  "bg-[var(--navy-deep)] text-white sm:col-span-2 lg:col-span-1"
];

function DomainBento({
  domains,
  isPending
}: {
  domains: DomainSummary[];
  isPending: boolean;
}) {
  if (isPending) {
    return (
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Skeleton />
        <Skeleton />
        <Skeleton />
        <Skeleton />
      </div>
    );
  }

  if (!domains.length) {
    return (
      <p className="mt-8 text-muted-foreground">
        Les domaines seront disponibles prochainement.
      </p>
    );
  }

  return (
    <div className="mt-8 grid auto-rows-[minmax(10rem,auto)] gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {domains.slice(0, 5).map((domain, index) => (
        <a
          key={domain.id}
          href={`/domaines/${domain.slug}`}
          className={`group relative flex min-h-40 flex-col justify-between overflow-hidden rounded-lg border border-border p-5 shadow-editorial transition hover:-translate-y-0.5 hover:shadow-editorial-lg ${DOMAIN_TONES[index]}`}
        >
          <span className="h-1 w-12 gabon-stripe" aria-hidden="true" />
          <div className="mt-8">
            <p className="text-xs font-semibold uppercase opacity-70">
              Domaine academique
            </p>
            <h3 className={`mt-2 font-display font-semibold leading-tight ${index === 0 ? "text-3xl" : "text-xl"}`}>
              {domain.name}
            </h3>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold">
              Explorer
              <ArrowRight className="size-4 transition group-hover:translate-x-1" />
            </span>
          </div>
        </a>
      ))}
    </div>
  );
}

export function HomePage() {
  const featured = useDocuments({ page_size: 4 });
  const domains = useDomains();
  const impactCues = [
    {
      icon: BookOpen,
      value: featured.data?.count ?? "-",
      label: "documents dans le catalogue"
    },
    {
      icon: LibraryBig,
      value: domains.data?.count ?? "-",
      label: "domaines academiques"
    },
    {
      icon: ShieldCheck,
      value: "V1",
      label: "lecture diffusee par sessions securisees"
    }
  ];

  return (
    <SiteLayout>
      <main>
        <section className="relative isolate min-h-[34rem] overflow-hidden border-b border-border bg-[var(--navy)] text-white sm:min-h-[36rem] lg:min-h-[min(42rem,calc(100svh-7rem))]">
          <div className="h-1 gabon-stripe" aria-hidden="true" />
          <div className="absolute inset-0 -z-20 overflow-hidden">
            <KenBurnsImage
              src="/images/hero-accueil.png"
              alt="Etudiants et chercheurs gabonais sur un campus universitaire"
              className="object-[58%_center] sm:object-center"
            />
          </div>
          <div className="absolute inset-0 -z-10 bg-[var(--navy-deep)]/72" aria-hidden="true" />
          <div className="container-editorial flex min-h-[33.75rem] items-center py-12 sm:min-h-[35.75rem] lg:min-h-[min(41.75rem,calc(100svh-7.25rem))]">
            <div className="max-w-3xl">
              <p className="text-sm font-semibold uppercase text-[var(--gold)]">
                Bibliotheque academique nationale
              </p>
              <h1 className="mt-4 font-display text-5xl font-semibold leading-tight sm:text-6xl">
                BiblioGABON
              </h1>
              <p className="mt-5 max-w-2xl text-lg text-white/85">
                Recherchez et lisez les ressources academiques produites au
                Gabon, dans un catalogue pense pour les etudiants et chercheurs.
              </p>
              <form
                action="/recherche"
                className="mt-8 flex max-w-2xl flex-col gap-2 rounded-lg bg-white p-2 shadow-editorial sm:flex-row"
              >
                <label className="sr-only" htmlFor="home-search">
                  Rechercher dans le catalogue
                </label>
                <input
                  id="home-search"
                  name="q"
                  placeholder="Titre, auteur ou domaine"
                  className="min-w-0 flex-1 rounded-lg px-3 py-2.5 text-[var(--navy)] outline-none"
                />
                <button className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--green)] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[var(--navy)]">
                  <Search className="size-4" />
                  Rechercher
                </button>
              </form>
              <a
                href="/catalogue"
                className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-white hover:text-[var(--gold)]"
              >
                Parcourir tout le catalogue
                <ArrowRight className="size-4" />
              </a>
            </div>
          </div>
        </section>

        <section aria-label="Impact de la bibliotheque" className="border-b border-border bg-white">
          <Reveal className="container-editorial grid divide-y divide-border py-2 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {impactCues.map(({ icon: Icon, value, label }) => (
              <div key={label} className="flex items-center gap-4 px-2 py-5 sm:px-5">
                <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg bg-[var(--green-soft)] text-[var(--green)]">
                  <Icon className="size-5" />
                </span>
                <div>
                  <p className="font-display text-2xl font-semibold text-[var(--navy)]">{value}</p>
                  <p className="text-sm text-muted-foreground">{label}</p>
                </div>
              </div>
            ))}
          </Reveal>
        </section>

        <section className="border-b border-border bg-[var(--surface-alt)]">
          <Reveal className="container-editorial py-14 sm:py-20">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div className="max-w-2xl">
                <p className="text-sm font-semibold uppercase text-[var(--green)]">
                  Disciplines
                </p>
                <h2 className="mt-2 font-display text-3xl font-semibold text-[var(--navy)] sm:text-4xl">
                  Le savoir gabonais par domaine
                </h2>
                <p className="mt-3 text-muted-foreground">
                  Explorez le catalogue selon votre champ d'etude ou de recherche.
                </p>
              </div>
              <a href="/domaines" className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--navy)] hover:text-[var(--green)]">
                Tous les domaines
                <ArrowRight className="size-4" />
              </a>
            </div>
            <DomainBento
              domains={domains.data?.results ?? []}
              isPending={domains.isPending}
            />
          </Reveal>
        </section>

        <section className="bg-white">
          <Reveal className="container-editorial py-14 sm:py-20">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase text-[var(--green)]">
                  Selection
                </p>
                <h2 className="mt-2 font-display text-3xl font-semibold text-[var(--navy)] sm:text-4xl">
                  Documents a la une
                </h2>
              </div>
              <a href="/catalogue" className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--navy)] hover:text-[var(--green)]">
                Voir le catalogue
                <ArrowRight className="size-4" />
              </a>
            </div>
            {featured.isPending ? (
              <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                <Skeleton />
                <Skeleton />
                <Skeleton />
                <Skeleton />
              </div>
            ) : featured.data?.results.length ? (
              <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                {featured.data.results.map((document) => (
                  <DocumentCard key={document.id} document={document} />
                ))}
              </div>
            ) : (
              <p className="mt-8 text-muted-foreground">
                Les documents a la une seront disponibles prochainement.
              </p>
            )}
          </Reveal>
        </section>
      </main>
    </SiteLayout>
  );
}
