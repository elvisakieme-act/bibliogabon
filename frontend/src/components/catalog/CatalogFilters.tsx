import type { DomainSummary } from "@/api/types";

type FilterValues = Record<string, string | undefined>;

/**
 * Les critères du catalogue.
 *
 * Le panneau menait toujours à la recherche : on croyait affiner une liste et
 * l'on changeait de page. Il sert maintenant les deux écrans, et chacun reçoit
 * ce qu'il sait traiter — le catalogue filtre et ordonne son fonds, la
 * recherche y ajoute les mots. Un champ qui part vers un point d'entrée
 * incapable de le lire serait ignoré en silence, c'est-à-dire la faute qu'on
 * vient de corriger.
 */
export function CatalogFilters({
  values,
  domains = [],
  variant = "inline",
  action = "/recherche",
  withQuery = true,
  withOrdering = false
}: {
  values: FilterValues;
  domains?: DomainSummary[];
  variant?: "inline" | "sidebar";
  action?: string;
  /** Le champ de mots : la recherche seule sait l'honorer. */
  withQuery?: boolean;
  /** L'ordre de la liste : le catalogue seul l'offre, la recherche classe par pertinence. */
  withOrdering?: boolean;
}) {
  const formClassName =
    variant === "sidebar"
      ? "grid gap-4 rounded-lg border border-border bg-white p-5 shadow-editorial"
      : "grid gap-3 rounded-lg border border-border bg-white p-4 shadow-editorial md:grid-cols-2 lg:grid-cols-3";

  return (
    <form action={action} className={formClassName}>
      {withQuery ? (
        <label className="text-sm font-semibold text-[var(--navy)]">
          Recherche
          <input
            name="q"
            defaultValue={values.q}
            placeholder="Titre, auteur, sujet"
            className="mt-1.5 w-full rounded-lg border border-border px-3 py-2 font-normal outline-none focus:border-[var(--green)]"
          />
        </label>
      ) : null}
      <label className="text-sm font-semibold text-[var(--navy)]">
        Domaine
        {/* `key` sur la liste des domaines : ils arrivent après le premier
            rendu, et `defaultValue` ne se réapplique pas aux options ajoutées
            ensuite. Le filtre s'appliquait donc bien tandis que le panneau
            affichait « Tous les domaines » — le lecteur ne pouvait pas savoir
            ce qui était actif, et « Appliquer » l'aurait effacé. */}
        <select
          key={`domain-${domains.length}`}
          name="domain"
          defaultValue={values.domain ?? ""}
          className="mt-1.5 w-full rounded-lg border border-border bg-white px-3 py-2 font-normal"
        >
          <option value="">Tous les domaines</option>
          {domains.map((domain) => (
            <option key={domain.id} value={domain.slug}>
              {domain.name}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm font-semibold text-[var(--navy)]">
        Langue
        <select
          name="language"
          defaultValue={values.language ?? ""}
          className="mt-1.5 w-full rounded-lg border border-border bg-white px-3 py-2 font-normal"
        >
          <option value="">Toutes les langues</option>
          <option value="fr">Français</option>
          <option value="en">Anglais</option>
        </select>
      </label>
      <label className="text-sm font-semibold text-[var(--navy)]">
        Accès
        <select
          name="access"
          defaultValue={values.access ?? ""}
          className="mt-1.5 w-full rounded-lg border border-border bg-white px-3 py-2 font-normal"
        >
          <option value="">Tous les accès</option>
          <option value="free">Libre</option>
          <option value="institution_only">Institution</option>
          <option value="subscription">Abonnement</option>
          <option value="sponsored">Sponsorisé</option>
          <option value="restricted">Restreint</option>
        </select>
      </label>
      <label className="text-sm font-semibold text-[var(--navy)]">
        Année
        <input
          name="year"
          inputMode="numeric"
          defaultValue={values.year}
          placeholder="2026"
          className="mt-1.5 w-full rounded-lg border border-border px-3 py-2 font-normal outline-none focus:border-[var(--green)]"
        />
      </label>
      {withOrdering ? (
        <label className="text-sm font-semibold text-[var(--navy)]">
          Trier par
          <select
            name="ordering"
            defaultValue={values.ordering ?? "title"}
            className="mt-1.5 w-full rounded-lg border border-border bg-white px-3 py-2 font-normal"
          >
            <option value="title">Titre</option>
            <option value="-published_at">Entrées récentes</option>
            <option value="-publication_year">Année de publication</option>
          </select>
        </label>
      ) : null}
      <div className="flex items-end">
        <button className="w-full rounded-lg bg-[var(--navy)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--navy-deep)]">
          {withQuery ? "Rechercher" : "Appliquer"}
        </button>
      </div>
    </form>
  );
}
