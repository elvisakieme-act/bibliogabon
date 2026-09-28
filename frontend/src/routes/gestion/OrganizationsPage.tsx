import { Link } from "@tanstack/react-router";

import { ApiError } from "@/api/client";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useStaffOrganizations } from "@/features/staff/hooks";

export function OrganizationsPage() {
  const query = useStaffOrganizations();

  if (query.isPending) {
    return <Skeleton label="Chargement des organisations" />;
  }
  if (query.isError) {
    return (
      <EmptyState
        title="Organisations indisponibles"
        description={
          query.error instanceof ApiError
            ? query.error.message
            : "La liste des organisations n'a pas pu etre chargee."
        }
      />
    );
  }

  const rows = query.data?.results ?? [];

  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">Organisations</h2>
      {rows.length === 0 ? (
        <EmptyState
          title="Aucune organisation"
          description="Vous n'administrez aucune organisation."
        />
      ) : (
        <ul className="divide-y divide-slate-100 rounded border border-slate-200 bg-white">
          {rows.map((organization) => (
            <li key={organization.id} className="flex items-center justify-between gap-3 p-4">
              <div>
                <Link
                  to="/gestion/organisations/$organizationId"
                  params={{ organizationId: String(organization.id) }}
                  className="font-medium underline decoration-slate-300"
                >
                  {organization.name}
                </Link>
                <p className="text-sm text-slate-600">{organization.organization_type}</p>
              </div>
              {organization.requires_identity_verification ? (
                <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs text-amber-900">
                  Vérification d&apos;identité exigée
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
