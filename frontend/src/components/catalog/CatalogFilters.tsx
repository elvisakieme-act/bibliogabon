import type { DomainSummary } from "@/api/types";

type FilterValues = Record<string, string | undefined>;

export function CatalogFilters({
  values,
  domains = [],
  variant = "inline"
}: {
  values: FilterValues;
  domains?: DomainSummary[];
  variant?: "inline" | "sidebar";
}) {
  const formClassName = variant === "sidebar"
    ? "grid gap-4 rounded-lg border border-border bg-white p-5 shadow-editorial"
    : "grid gap-3 rounded-lg border border-border bg-white p-4 shadow-editorial md:grid-cols-2 lg:grid-cols-3";

  return (
    <form action="/recherche" className={formClassName}>
      <label className="text-sm font-semibold text-[var(--navy)]">
        Recherche
        <input name="q" defaultValue={values.q} placeholder="Titre, auteur, sujet" className="mt-1.5 w-full rounded-lg border border-border px-3 py-2 font-normal outline-none focus:border-[var(--green)]" />
      </label>
      <label className="text-sm font-semibold text-[var(--navy)]">
        Domaine
        <select name="domain" defaultValue={values.domain ?? ""} className="mt-1.5 w-full rounded-lg border border-border bg-white px-3 py-2 font-normal">
          <option value="">Tous les domaines</option>
          {domains.map((domain) => <option key={domain.id} value={domain.slug}>{domain.name}</option>)}
        </select>
      </label>
      <label className="text-sm font-semibold text-[var(--navy)]">
        Langue
        <select name="language" defaultValue={values.language ?? ""} className="mt-1.5 w-full rounded-lg border border-border bg-white px-3 py-2 font-normal">
          <option value="">Toutes les langues</option>
          <option value="fr">Francais</option>
          <option value="en">Anglais</option>
        </select>
      </label>
      <label className="text-sm font-semibold text-[var(--navy)]">
        Acces
        <select name="access" defaultValue={values.access ?? ""} className="mt-1.5 w-full rounded-lg border border-border bg-white px-3 py-2 font-normal">
          <option value="">Tous les acces</option>
          <option value="free">Libre</option>
          <option value="institution_only">Institution</option>
          <option value="subscription">Abonnement</option>
          <option value="sponsored">Sponsorise</option>
          <option value="restricted">Restreint</option>
        </select>
      </label>
      <label className="text-sm font-semibold text-[var(--navy)]">
        Annee
        <input name="year" inputMode="numeric" defaultValue={values.year} placeholder="2026" className="mt-1.5 w-full rounded-lg border border-border px-3 py-2 font-normal outline-none focus:border-[var(--green)]" />
      </label>
      <div className="flex items-end">
        <button className="w-full rounded-lg bg-[var(--navy)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--navy-deep)]">
          Rechercher
        </button>
      </div>
    </form>
  );
}
