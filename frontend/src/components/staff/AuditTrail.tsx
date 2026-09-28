import { ApiError } from "@/api/client";
import { auditEventLabel, isKnownAuditEvent } from "@/components/staff/auditLabels";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocumentAudit } from "@/features/staff/hooks";

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("fr-FR");
}

/**
 * Journal d'audit d'un document.
 *
 * Le serveur filtre `metadata` par liste blanche, donc **aucun champ n'est
 * garanti présent** : l'écran lit ce qui est là et ne suppose rien. Un
 * événement sans acteur est l'oeuvre du système, pas une ligne à masquer.
 */
export function AuditTrail({ documentId }: { documentId: number }) {
  const query = useDocumentAudit(documentId);

  if (query.isPending) {
    return <Skeleton label="Chargement du journal" />;
  }
  if (query.isError) {
    return (
      <section className="rounded-[calc(var(--radius)+0.25rem)] border border-[var(--border)] bg-[var(--card)] p-5 shadow-editorial">
        <h3 className="font-display text-lg text-[var(--navy)]">Journal d&apos;audit</h3>
        <p className="mt-2 text-sm text-[var(--muted-foreground)]">
          {query.error instanceof ApiError
            ? query.error.message
            : "Le journal n'a pas pu être charge."}
        </p>
      </section>
    );
  }

  const events = query.data?.results ?? [];

  return (
    <section className="rounded-[calc(var(--radius)+0.25rem)] border border-[var(--border)] bg-[var(--card)] p-5 shadow-editorial">
      <h3 id="journal-titre" className="font-display text-lg text-[var(--navy)]">
        Journal d&apos;audit
      </h3>
      {events.length === 0 ? (
        <p className="mt-2 text-sm text-[var(--muted-foreground)]">
          Aucun événement enregistré.
        </p>
      ) : (
        <ul aria-labelledby="journal-titre" className="mt-3 space-y-3 text-sm">
          {events.map((event) => {
            const reason = event.metadata?.reason;
            return (
              <li key={event.id} className="border-l-2 border-[var(--border)] ps-3">
                <p
                  className={isKnownAuditEvent(event.event_type) ? "font-medium" : "font-mono"}
                >
                  {auditEventLabel(event.event_type)}
                </p>
                <p className="text-[var(--muted-foreground)]">
                  {event.actor?.display_name ?? "Système"} &middot;{" "}
                  {formatDate(event.created_at)}
                </p>
                {typeof reason === "string" && reason ? (
                  <p className="mt-1 text-[var(--ink)]">{reason}</p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
