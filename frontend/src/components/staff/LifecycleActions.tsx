import { useState } from "react";

import { ApiError } from "@/api/client";
import type { StaffDocument } from "@/api/types";
import { useArchiveStaffDocument, useWithdrawStaffDocument } from "@/features/staff/hooks";

type Action = "withdraw" | "archive";

const COPY: Record<Action, { open: string; title: string; label: string; confirm: string }> = {
  withdraw: {
    open: "Retirer du public",
    title: "Retrait du document",
    label: "Motif du retrait",
    confirm: "Confirmer le retrait"
  },
  archive: {
    open: "Archiver",
    title: "Archivage du document",
    label: "Motif de l'archivage",
    confirm: "Confirmer l'archivage"
  }
};

/**
 * Retrait et archivage.
 *
 * Chaque geste n'apparaît que dans les états où il a un sens : proposer de
 * retirer un brouillon ferait croire que le geste produit quelque chose. Le
 * serveur refuse de toute façon, mais un bouton inerte apprend la mauvaise
 * leçon.
 *
 * Les deux exigent un motif. Un document public qui disparaît sans raison
 * enregistrée est exactement ce qu'un audit sert à empêcher.
 */
export function LifecycleActions({
  document,
  documentId
}: {
  document: StaffDocument;
  documentId: number;
}) {
  const [open, setOpen] = useState<Action | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const withdraw = useWithdrawStaffDocument(documentId);
  const archive = useArchiveStaffDocument(documentId);

  const canWithdraw = document.publication_status === "published";
  const canArchive = ["published", "withdrawn"].includes(document.publication_status);
  if (!canWithdraw && !canArchive) return null;

  function start(action: Action) {
    setOpen(action);
    setReason("");
    setError("");
  }

  async function run(action: Action) {
    setError("");
    if (!reason.trim()) {
      setError("Un motif est obligatoire : il est conservé dans le journal d'audit.");
      return;
    }
    const mutation = action === "withdraw" ? withdraw : archive;
    try {
      await mutation.mutateAsync(reason.trim());
      setOpen(null);
      setReason("");
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "L'operation n'a pas pu aboutir. Réessayez."
      );
    }
  }

  return (
    <section className="space-y-3 rounded border border-slate-200 bg-white p-4">
      <h3 className="font-semibold">Fin de vie</h3>

      {open === null ? (
        <div className="flex flex-wrap gap-2">
          {canWithdraw ? (
            <button
              type="button"
              onClick={() => start("withdraw")}
              className="rounded border border-orange-300 px-3 py-1.5 text-sm text-orange-900"
            >
              {COPY.withdraw.open}
            </button>
          ) : null}
          {canArchive ? (
            <button
              type="button"
              onClick={() => start("archive")}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            >
              {COPY.archive.open}
            </button>
          ) : null}
        </div>
      ) : (
        <div className="space-y-3">
          <h4 className="text-sm font-medium">{COPY[open].title}</h4>
          {error ? (
            <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
              {error}
            </p>
          ) : null}
          <div className="flex flex-col gap-1">
            <label htmlFor="cycle-motif" className="text-sm font-medium">
              {COPY[open].label}
            </label>
            <textarea
              id="cycle-motif"
              rows={3}
              className="rounded border border-slate-300 px-2 py-1.5"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            <p className="text-xs text-slate-500">
              {open === "withdraw"
                ? "Le contenu est conservé : pages, version et droits restent en place. Seule la lecture publique cesse."
                : "L'archivage ferme le document sur la plateforme."}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => run(open)}
              disabled={withdraw.isPending || archive.isPending}
              className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {COPY[open].confirm}
            </button>
            <button
              type="button"
              onClick={() => setOpen(null)}
              className="rounded border border-slate-300 px-4 py-2 text-sm"
            >
              Annuler
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
