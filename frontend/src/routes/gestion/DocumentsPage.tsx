import { Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";

import { ApiError } from "@/api/client";
import type { StaffDocumentFilters } from "@/api/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { DocumentStateBadge } from "@/components/staff/DocumentStateBadge";
import { PUBLICATION_STATUS_OPTIONS } from "@/components/staff/publicationStatus";
import { useDocumentTypes, useDomains } from "@/features/catalog/hooks";
import { useStaffDocuments } from "@/features/staff/hooks";

const PAGE_SIZE = 20;

export function DocumentsPage() {
  const [filters, setFilters] = useState<StaffDocumentFilters>({});
  const [page, setPage] = useState(1);
  const domains = useDomains();
  const types = useDocumentTypes();
  const query = useStaffDocuments(
    useMemo(() => ({ ...filters, page: page > 1 ? page : undefined }), [filters, page])
  );

  // Changer un filtre depuis la page 3 d'un resultat qui n'en compte plus
  // qu'une afficherait une liste vide, indistinguable de « aucun document ».
  function setFilter(key: keyof StaffDocumentFilters, value: string) {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value || undefined }));
  }

  const count = query.data?.count ?? 0;
  const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Documents</h2>
        <Link
          to="/gestion/documents/nouveau"
          className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
        >
          Nouveau document
        </Link>
      </div>

      <form
        className="grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-4"
        onSubmit={(event) => event.preventDefault()}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="filtre-état" className="text-sm font-medium">
            État
          </label>
          <select
            id="filtre-état"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={filters.status ?? ""}
            onChange={(event) => setFilter("status", event.target.value)}
          >
            <option value="">Tous</option>
            {PUBLICATION_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="filtre-domaine" className="text-sm font-medium">
            Domaine
          </label>
          <select
            id="filtre-domaine"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={filters.domain ?? ""}
            onChange={(event) => setFilter("domain", event.target.value)}
          >
            <option value="">Tous</option>
            {(domains.data?.results ?? []).map((domain) => (
              <option key={domain.slug} value={domain.slug}>
                {domain.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="filtre-type" className="text-sm font-medium">
            Type
          </label>
          <select
            id="filtre-type"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={filters.type ?? ""}
            onChange={(event) => setFilter("type", event.target.value)}
          >
            <option value="">Tous</option>
            {(types.data?.results ?? []).map((type) => (
              <option key={type.slug} value={type.slug}>
                {type.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="filtre-titre" className="text-sm font-medium">
            Titre
          </label>
          <input
            id="filtre-titre"
            type="search"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={filters.q ?? ""}
            onChange={(event) => setFilter("q", event.target.value)}
          />
        </div>
      </form>

      <DocumentsResult query={query} />

      {count > 0 ? (
        <div className="flex items-center justify-between gap-3 text-sm">
          <p>
            {count} document{count > 1 ? "s" : ""} &middot; page {page} sur {lastPage}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded border border-slate-300 px-3 py-1.5 disabled:opacity-40"
              disabled={!query.data?.previous}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
            >
              Page precedente
            </button>
            <button
              type="button"
              className="rounded border border-slate-300 px-3 py-1.5 disabled:opacity-40"
              disabled={!query.data?.next}
              onClick={() => setPage((current) => current + 1)}
            >
              Page suivante
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function DocumentsResult({ query }: { query: ReturnType<typeof useStaffDocuments> }) {
  if (query.isPending) {
    return <Skeleton label="Chargement des documents" />;
  }
  if (query.isError) {
    // Un refus doit se lire comme un refus. Le rendre en liste vide
    // ferait croire a un catalogue vide et cacherait la vraie cause.
    const error = query.error;
    return (
      <EmptyState
        title="Liste indisponible"
        description={
          error instanceof ApiError
            ? error.message
            : "La liste des documents n'a pas pu être chargee."
        }
      />
    );
  }
  const rows = query.data?.results ?? [];
  if (rows.length === 0) {
    return (
      <EmptyState
        title="Aucun document"
        description="Aucun document ne correspond a ces filtres."
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded border border-slate-200 bg-white">
      <table className="w-full min-w-3xl border-collapse text-sm">
        <caption className="sr-only">Documents de votre périmètre</caption>
        <thead className="bg-slate-50 text-left">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">
              Titre
            </th>
            <th scope="col" className="px-4 py-2 font-medium">
              État
            </th>
            <th scope="col" className="px-4 py-2 font-medium">
              Domaine
            </th>
            <th scope="col" className="px-4 py-2 font-medium">
              Type
            </th>
            <th scope="col" className="px-4 py-2 font-medium">
              Pages
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((document) => (
            <tr key={document.id} className="border-t border-slate-100">
              <th scope="row" className="px-4 py-2 text-left font-normal">
                <Link
                  to="/gestion/documents/$documentId"
                  params={{ documentId: String(document.id) }}
                  className="text-slate-900 underline decoration-slate-300 hover:decoration-slate-900"
                >
                  {document.title}
                </Link>
              </th>
              <td className="px-4 py-2">
                <DocumentStateBadge status={document.publication_status} />
              </td>
              <td className="px-4 py-2">{document.academic_domain?.name ?? "—"}</td>
              <td className="px-4 py-2">{document.document_type?.name ?? "—"}</td>
              {/* Le nombre de pages, jamais le libelle de version ni rien qui
                  approche d'une clé de stockage. */}
              <td className="px-4 py-2">{document.ingestion?.page_count ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
