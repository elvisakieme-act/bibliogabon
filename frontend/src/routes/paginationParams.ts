const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 12;
const MAX_PAGE_SIZE = 50;

function clampedInteger(value: string | null, fallback: number, maximum?: number) {
  if (value === null || value.trim() === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  const integer = Math.max(1, Math.trunc(parsed));
  return maximum === undefined ? integer : Math.min(integer, maximum);
}

/**
 * Les critères de catalogue lus dans l'adresse.
 *
 * Ils y vivent plutôt que dans un état React : une liste filtrée doit pouvoir
 * se partager, se mettre en favori et survivre à un rechargement. Seules les
 * clés que le point d'entrée connaît sont relayées — en relayer une qu'il
 * ignore la ferait disparaître en silence, ce qui est précisément le défaut
 * qu'on vient de corriger côté serveur.
 */
export const CATALOG_FILTER_KEYS = ["domain", "language", "access", "year", "type"] as const;

export function catalogFiltersFromSearch(searchStr: string): Record<string, string> {
  const search = new URLSearchParams(searchStr);
  const filtres: Record<string, string> = {};
  for (const cle of CATALOG_FILTER_KEYS) {
    const valeur = search.get(cle)?.trim();
    if (valeur) filtres[cle] = valeur;
  }
  const ordering = search.get("ordering")?.trim();
  if (ordering) filtres.ordering = ordering;
  return filtres;
}

export function paginationFromSearch(searchStr: string) {
  const search = new URLSearchParams(searchStr);
  return {
    page: clampedInteger(search.get("page"), DEFAULT_PAGE),
    pageSize: clampedInteger(search.get("page_size"), DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
  };
}
