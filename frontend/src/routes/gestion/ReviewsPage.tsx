import { Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";

import { ApiError } from "@/api/client";
import type { StaffReviewFilters } from "@/api/types";
import { completenessLabel } from "@/components/staff/completeness";
import { DocumentStateBadge } from "@/components/staff/DocumentStateBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useStaffReviews } from "@/features/staff/hooks";

const REVIEW_STATUS_OPTIONS = [
  { value: "open", label: "En attente" },
  { value: "approved", label: "Approuvés" },
  { value: "rejected", label: "Rejetés" },
  { value: "cancelled", label: "Annulés" }
] as const;

const ASSIGNMENT_OPTIONS = [
  { value: "any", label: "Peu importe" },
  { value: "me", label: "À moi" },
  { value: "none", label: "Non attribués" }
] as const;

export function ReviewsPage() {
  const [filters, setFilters] = useState<StaffReviewFilters>({ status: "open" });
  const query = useStaffReviews(useMemo(() => filters, [filters]));

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">File de revue</h2>
        <p className="text-sm text-slate-600">
          Les dossiers soumis, et ce qui bloque encore leur publication. Un document dont vous
          êtes auteur ne peut pas être décidé par vous.
        </p>
      </div>

      <form
        className="grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2"
        onSubmit={(event) => event.preventDefault()}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="revue-etat" className="text-sm font-medium">
            État
          </label>
          <select
            id="revue-etat"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={filters.status ?? "open"}
            onChange={(event) =>
              setFilters((current) => ({
                ...current,
                status: event.target.value as StaffReviewFilters["status"]
              }))
            }
          >
            {REVIEW_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="revue-attribution" className="text-sm font-medium">
            Attribution
          </label>
          <select
            id="revue-attribution"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={filters.assigned ?? "any"}
            onChange={(event) =>
              setFilters((current) => ({
                ...current,
                assigned: event.target.value as StaffReviewFilters["assigned"]
              }))
            }
          >
            {ASSIGNMENT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </form>

      <ReviewsResult query={query} />
    </section>
  );
}

function ReviewsResult({ query }: { query: ReturnType<typeof useStaffReviews> }) {
  if (query.isPending) {
    return <Skeleton label="Chargement de la file" />;
  }
  if (query.isError) {
    // Un refus se lit comme un refus. Le rendre en file vide ferait croire
    // qu'il n'y a rien à relire, ce qui est faux et rassurant à tort.
    return (
      <EmptyState
        title="File indisponible"
        description={
          query.error instanceof ApiError
            ? query.error.message
            : "La file de revue n'a pas pu etre chargee."
        }
      />
    );
  }
  const rows = query.data?.results ?? [];
  if (rows.length === 0) {
    return (
      <EmptyState
        title="Aucun dossier en attente"
        description="Rien ne correspond à ces filtres."
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded border border-slate-200 bg-white">
      <table className="w-full min-w-3xl border-collapse text-sm">
        <caption className="sr-only">Dossiers en revue</caption>
        <thead className="bg-slate-50 text-left">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">
              Document
            </th>
            <th scope="col" className="px-4 py-2 font-medium">
              Auteurs
            </th>
            <th scope="col" className="px-4 py-2 font-medium">
              État
            </th>
            <th scope="col" className="px-4 py-2 font-medium">
              Relecteur
            </th>
            <th scope="col" className="px-4 py-2 font-medium">
              Ce qui bloque
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((review) => (
            <tr key={review.id} className="border-t border-slate-100 align-top">
              <th scope="row" className="px-4 py-2 text-left font-normal">
                <Link
                  to="/gestion/revues/$reviewId"
                  params={{ reviewId: String(review.id) }}
                  className="text-slate-900 underline decoration-slate-300 hover:decoration-slate-900"
                >
                  {review.document.title}
                </Link>
              </th>
              <td className="px-4 py-2">
                {review.document.authors.map((author) => author.display_name).join(", ") || "—"}
              </td>
              <td className="px-4 py-2">
                <DocumentStateBadge status={review.document.publication_status} />
              </td>
              <td className="px-4 py-2">{review.reviewer?.display_name ?? "Non attribué"}</td>
              <td className="px-4 py-2">
                {review.document.missing_for_publication.length === 0 ? (
                  <span className="text-emerald-700">Prêt à publier</span>
                ) : (
                  <ul className="space-y-0.5 text-amber-900">
                    {review.document.missing_for_publication.map((code) => (
                      <li key={code}>{completenessLabel(code)}</li>
                    ))}
                  </ul>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
