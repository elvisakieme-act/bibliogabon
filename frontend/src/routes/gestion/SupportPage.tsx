import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { ApiError } from "@/api/client";
import type { StaffTicket, StaffTicketFilters } from "@/api/types";
import {
  isKnownTicketCategory,
  TICKET_CATEGORY_OPTIONS,
  TICKET_STATUS_OPTIONS,
  ticketCategoryLabel,
  ticketPriorityLabel,
  ticketStatusLabel
} from "@/components/staff/ticketLabels";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useResolveStaffTicket, useStaffTickets } from "@/features/staff/hooks";

export function SupportPage() {
  const [filters, setFilters] = useState<StaffTicketFilters>({ status: "open" });
  const query = useStaffTickets(filters);

  function setFilter(key: keyof StaffTicketFilters, value: string) {
    setFilters((current) => ({ ...current, [key]: value || undefined }));
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Support et signalements</h2>
        <p className="text-sm text-slate-600">
          Demandes de support, signalements de documents et demandes de retrait. Un
          administrateur d&apos;organisation ne voit que celles de la sienne.
        </p>
      </div>

      <form
        className="grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2"
        onSubmit={(event) => event.preventDefault()}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="ticket-categorie" className="text-sm font-medium">
            Catégorie
          </label>
          <select
            id="ticket-categorie"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={filters.category ?? ""}
            onChange={(event) => setFilter("category", event.target.value)}
          >
            <option value="">Toutes</option>
            {TICKET_CATEGORY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="ticket-etat" className="text-sm font-medium">
            État
          </label>
          <select
            id="ticket-etat"
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
            value={filters.status ?? ""}
            onChange={(event) => setFilter("status", event.target.value)}
          >
            <option value="">Tous</option>
            {TICKET_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </form>

      <TicketsResult query={query} />
    </section>
  );
}

function TicketsResult({ query }: { query: ReturnType<typeof useStaffTickets> }) {
  if (query.isPending) {
    return <Skeleton label="Chargement de la file de support" />;
  }
  if (query.isError) {
    return (
      <EmptyState
        title="File indisponible"
        description={
          query.error instanceof ApiError
            ? query.error.message
            : "La file de support n'a pas pu être chargee."
        }
      />
    );
  }
  const rows = query.data?.results ?? [];
  if (rows.length === 0) {
    return (
      <EmptyState title="Aucune demande" description="Rien ne correspond à ces filtres." />
    );
  }

  return (
    <ul className="space-y-3">
      {rows.map((ticket) => (
        <TicketCard key={ticket.id} ticket={ticket} />
      ))}
    </ul>
  );
}

function TicketCard({ ticket }: { ticket: StaffTicket }) {
  const resolve = useResolveStaffTicket();
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState("");
  const [error, setError] = useState("");

  async function confirm() {
    setError("");
    if (!summary.trim()) {
      setError("Un résumé de la résolution est obligatoire : il est conservé au journal.");
      return;
    }
    try {
      await resolve.mutateAsync({ ticketId: ticket.id, summary: summary.trim() });
      setOpen(false);
      setSummary("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "L'operation n'a pas pu aboutir.");
    }
  }

  return (
    <li
      aria-label={ticket.title}
      className="space-y-3 rounded border border-slate-200 bg-white p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p
            className={
              isKnownTicketCategory(ticket.category)
                ? "text-sm text-slate-500"
                : "font-mono text-sm"
            }
          >
            {ticketCategoryLabel(ticket.category)}
          </p>
          <h3 className="font-medium">{ticket.title}</h3>
          <p className="text-sm text-slate-600">
            {ticket.created_by?.display_name ?? "Système"} &middot;{" "}
            {ticketStatusLabel(ticket.status)} &middot; {ticketPriorityLabel(ticket.priority)}
          </p>
        </div>
        {ticket.status !== "resolved" && ticket.status !== "cancelled" ? (
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            onClick={() => {
              setOpen(true);
              setSummary("");
              setError("");
            }}
          >
            Résoudre
          </button>
        ) : null}
      </div>

      <p className="text-sm text-slate-700">{ticket.description}</p>

      {ticket.document ? (
        <p className="text-sm">
          <Link
            to="/gestion/documents/$documentId"
            params={{ documentId: String(ticket.document.id) }}
            className="underline decoration-slate-300"
          >
            {ticket.document.title}
          </Link>
        </p>
      ) : null}

      {ticket.category === "withdrawal_request" ? (
        // Un modérateur qui croit qu'en fermant le ticket il a retiré le
        // document laissera en ligne un contenu dont le retrait a été accordé.
        <p className="rounded bg-amber-50 p-3 text-sm text-amber-900">
          Résoudre cette demande <strong>ne retire pas le document</strong>. Le retrait est un
          acte séparé, à faire depuis la fiche du document, avec son propre motif.
        </p>
      ) : null}

      {ticket.resolution_summary ? (
        <p className="text-sm text-emerald-800">{ticket.resolution_summary}</p>
      ) : null}

      {open ? (
        <div className="space-y-3 border-t border-slate-100 pt-3">
          {error ? (
            <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
              {error}
            </p>
          ) : null}
          <div className="flex flex-col gap-1">
            <label htmlFor={`resolution-${ticket.id}`} className="text-sm font-medium">
              Résumé de la résolution
            </label>
            <textarea
              id={`resolution-${ticket.id}`}
              rows={3}
              className="rounded border border-slate-300 px-2 py-1.5"
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={confirm}
              disabled={resolve.isPending}
              className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Confirmer la résolution
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded border border-slate-300 px-4 py-2 text-sm"
            >
              Annuler
            </button>
          </div>
        </div>
      ) : null}
    </li>
  );
}
