import { ApiError } from "@/api/client";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocumentIngestion } from "@/features/staff/hooks";

/**
 * Suivi du traitement.
 *
 * C'est le seul endroit du produit où un utilisateur attend un worker. Une
 * attente sans fin ni raison y est un défaut, pas un détail d'habillage :
 * l'écran dit dans quel état on est, ce qui a échoué, et combien de fois le
 * système a réessayé avant d'abandonner.
 *
 * Le sondage s'arrête de lui-même dès que le travail aboutit ou échoue —
 * continuer d'interroger un état terminal chargerait le serveur pour rien.
 */
export function IngestionStatus({ documentId }: { documentId: number }) {
  const query = useDocumentIngestion(documentId);

  if (query.isPending) {
    return <Skeleton label="Chargement du suivi de traitement" />;
  }
  if (query.isError || !query.data) {
    return (
      <section className="rounded border border-slate-200 bg-white p-4">
        <h3 className="font-semibold">Traitement</h3>
        <p className="mt-2 text-sm text-slate-600">
          {query.error instanceof ApiError
            ? query.error.message
            : "Le suivi du traitement n'a pas pu être charge."}
        </p>
      </section>
    );
  }

  const { state, version, job } = query.data;

  return (
    <section className="space-y-3 rounded border border-slate-200 bg-white p-4">
      <h3 className="font-semibold">Traitement</h3>

      {state === "no_source" ? (
        <p className="text-sm text-slate-600">
          Aucun fichier n&apos;a encore ete recu pour ce document.
        </p>
      ) : null}

      {state === "in_progress" ? (
        <div aria-live="polite" className="space-y-1">
          <p className="text-sm text-amber-900">
            Traitement en cours. Découpage des pages, extraction du texte, reconnaissance
            optique si nécessaire.
          </p>
          {job && job.retry_count > 0 ? (
            <p className="text-xs text-slate-600">
              {job.retry_count} tentative{job.retry_count > 1 ? "s" : ""} après echec.
            </p>
          ) : null}
        </div>
      ) : null}

      {state === "ready" && version ? (
        <p className="text-sm text-emerald-800">
          Version {version.version_label} traitée : {version.page_count ?? 0} page
          {(version.page_count ?? 0) > 1 ? "s" : ""} lisibles et indexees.
        </p>
      ) : null}

      {state === "failed" ? (
        <div className="space-y-2">
          <p className="text-sm font-medium text-red-800">Le traitement a échoué.</p>
          {job?.error_message ? (
            <p className="text-sm text-red-800">{job.error_message}</p>
          ) : null}
          {job && job.retry_count > 0 ? (
            <p className="text-xs text-slate-600">
              {job.retry_count} tentative{job.retry_count > 1 ? "s" : ""} avant abandon.
            </p>
          ) : null}
          <p className="text-sm text-slate-600">
            Déposez a nouveau le fichier source, en cochant le remplacement de la version.
          </p>
        </div>
      ) : null}
    </section>
  );
}
