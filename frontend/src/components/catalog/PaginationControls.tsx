import type { PaginatedResponse } from "@/api/types";

type Params = Record<string, string | number | undefined>;

function pageHref(path: string, params: Params, page: number, pageSize: number) {
  const search = new URLSearchParams();
  Object.entries({ ...params, page, page_size: pageSize }).forEach(([key, value]) => {
    if (value !== undefined && String(value) !== "") search.set(key, String(value));
  });
  return `${path}?${search.toString()}`;
}

export function PaginationControls({ response, page, pageSize, path, params = {} }: { response: PaginatedResponse<unknown>; page: number; pageSize: number; path: string; params?: Params }) {
  const hasResults = response.count > 0;
  const totalPages = Math.max(1, Math.ceil(response.count / pageSize));

  return (
    <nav aria-label="Pagination" className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
      <p className="text-sm text-muted-foreground">{hasResults ? `${response.count} resultat${response.count > 1 ? "s" : ""}` : "Aucun resultat"}</p>
      <div className="flex items-center gap-2">
        {response.previous ? <a href={pageHref(path, params, page - 1, pageSize)} className="rounded-lg border border-border px-3 py-2 text-sm font-semibold text-[var(--navy)]">Precedent</a> : <span className="rounded-lg border border-border px-3 py-2 text-sm text-muted-foreground">Precedent</span>}
        <span className="text-sm text-muted-foreground">Page {page} sur {totalPages}</span>
        {response.next ? <a href={pageHref(path, params, page + 1, pageSize)} className="rounded-lg border border-border px-3 py-2 text-sm font-semibold text-[var(--navy)]">Suivant</a> : <span className="rounded-lg border border-border px-3 py-2 text-sm text-muted-foreground">Suivant</span>}
        <select aria-label="Resultats par page" defaultValue={pageSize} onChange={(event) => { window.location.href = pageHref(path, params, 1, Number(event.target.value)); }} className="rounded-lg border border-border bg-white px-2 py-2 text-sm"><option value="8">8</option><option value="12">12</option><option value="24">24</option></select>
      </div>
    </nav>
  );
}
