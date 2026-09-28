import { Link, useParams } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "@/api/client";
import type { StaffReview } from "@/api/types";
import { completenessLabel } from "@/components/staff/completeness";
import { DocumentStateBadge } from "@/components/staff/DocumentStateBadge";
import { authorizationStatusLabel } from "@/components/staff/rightsOptions";
import { EmptyState } from "@/components/ui/EmptyState";
import { FieldErrors } from "@/components/ui/FieldErrors";
import { fieldErrorId, fieldErrorProps } from "@/components/ui/fieldErrors";
import { Skeleton } from "@/components/ui/Skeleton";
import { applyApiErrors, toFieldErrors } from "@/features/staff/applyApiErrors";
import {
  useAssignStaffReview,
  useDecideStaffReview,
  useStaffReview
} from "@/features/staff/hooks";

export function ReviewDetailPage() {
  const { reviewId } = useParams({ from: "/gestion/revues/$reviewId" });
  const query = useStaffReview(Number(reviewId));

  if (query.isPending) {
    return <Skeleton label="Chargement du dossier" />;
  }
  if (query.isError || !query.data) {
    return (
      <EmptyState
        title="Dossier indisponible"
        description={
          query.error instanceof ApiError
            ? query.error.message
            : "Ce dossier n'a pas pu être charge."
        }
      />
    );
  }

  return <ReviewDetail review={query.data} />;
}

function ReviewDetail({ review }: { review: StaffReview }) {
  const document = review.document;
  const assign = useAssignStaffReview(review.id);
  const blocking = document.missing_for_publication;

  return (
    <div className="max-w-3xl space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold">{document.title}</h2>
          <DocumentStateBadge status={document.publication_status} />
        </div>
        <p className="text-sm text-slate-600">
          Déposé par {document.authors.map((author) => author.display_name).join(", ") || "—"}
          {" · "}
          <Link
            to="/gestion/documents/$documentId"
            params={{ documentId: String(document.id) }}
            className="underline decoration-slate-300"
          >
            Voir la fiche complète
          </Link>
        </p>
      </header>

      <section className="grid gap-4 rounded border border-slate-200 bg-white p-4 sm:grid-cols-3">
        <div>
          <h3 className="text-sm font-medium text-slate-500">Droits</h3>
          {/* Affichés, jamais décidés ici : D014 a fait de
              `RightsAgreement.authorization_status` la seule représentation de
              cette barrière, et une seconde commande serait une seconde
              réponse à une même question. La décision se prend sur la fiche. */}
          <p className="mt-1">
            {document.rights
              ? authorizationStatusLabel(document.rights.authorization_status)
              : "Aucune déclaration"}
          </p>
          {document.rights ? (
            <p className="text-xs text-slate-500">{document.rights.rights_holder_name}</p>
          ) : null}
        </div>
        <div>
          <h3 className="text-sm font-medium text-slate-500">Traitement</h3>
          <p className="mt-1">{document.ingestion?.status ?? "Aucun fichier"}</p>
        </div>
        <div>
          <h3 className="text-sm font-medium text-slate-500">Pages</h3>
          <p className="mt-1">{document.ingestion?.page_count ?? "—"}</p>
        </div>
      </section>

      <section className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-slate-600">
          Relecteur : {review.reviewer?.display_name ?? "non attribué"}
        </span>
        <button
          type="button"
          disabled={assign.isPending || review.status !== "open"}
          onClick={() => assign.mutate()}
          className="rounded border border-slate-300 px-3 py-1.5 disabled:opacity-40"
        >
          Me saisir du dossier
        </button>
      </section>

      {blocking.length > 0 ? (
        <section className="rounded border border-amber-300 bg-amber-50 p-4">
          <h3 id="blocage-titre" className="text-sm font-semibold text-amber-900">
            L&apos;approbation est bloquée par
          </h3>
          <ul aria-labelledby="blocage-titre" className="mt-2 space-y-1 text-sm text-amber-900">
            {blocking.map((code) => (
              <li key={code}>{completenessLabel(code)}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <DecisionForm review={review} />
    </div>
  );
}

interface DecisionValues {
  reason: string;
}

const FIELDS = ["reason", "decision"] as const;

function DecisionForm({ review }: { review: StaffReview }) {
  const decide = useDecideStaffReview(review.id, review.document.id);
  const [formError, setFormError] = useState("");
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    getValues,
    formState: { errors, isSubmitting }
  } = useForm<DecisionValues>({ defaultValues: { reason: "" } });
  const fieldErrors = toFieldErrors(errors);
  const blocked = review.document.missing_for_publication.length > 0;
  const closed = review.status !== "open";

  async function submit(decision: "approved" | "rejected" | "cancelled") {
    clearErrors();
    setFormError("");
    const reason = getValues("reason").trim();
    if (decision === "rejected" && !reason) {
      // Refusé avant l'appel : le serveur le refuserait aussi, mais un
      // aller-retour pour apprendre ce qu'on savait déjà est du temps perdu.
      setError("reason", {
        type: "required",
        message: "Un rejet doit être motivé, pour l'audit interne."
      });
      return;
    }
    try {
      await decide.mutateAsync({ decision, reason });
    } catch (caught) {
      setFormError(applyApiErrors(caught, { setError, fields: FIELDS }));
    }
  }

  if (closed) {
    return (
      <section className="rounded border border-slate-200 bg-white p-4 text-sm">
        <h3 className="font-semibold">Décision rendue</h3>
        <p className="mt-2 text-slate-700">
          {review.decided_by?.display_name ?? "Un modérateur"} a statué :{" "}
          {review.status === "approved" ? "approuvé" : review.status}.
        </p>
        {review.decision_reason ? (
          <p className="mt-1 text-slate-600">{review.decision_reason}</p>
        ) : null}
      </section>
    );
  }

  return (
    <form
      onSubmit={handleSubmit(() => undefined)}
      noValidate
      className="space-y-4 rounded border border-slate-200 bg-white p-4"
    >
      <h3 className="font-semibold">Décision</h3>
      {formError ? (
        <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
          {formError}
        </p>
      ) : null}

      <div className="flex flex-col gap-1">
        <label htmlFor="decision-motif" className="text-sm font-medium">
          Motif de la décision
        </label>
        <textarea
          id="decision-motif"
          rows={3}
          className="rounded border border-slate-300 px-2 py-1.5"
          {...register("reason")}
          {...fieldErrorProps("decision", "reason", fieldErrors)}
          aria-describedby={
            fieldErrors.reason?.length ? fieldErrorId("decision", "reason") : undefined
          }
        />
        <FieldErrors form="decision" field="reason" fieldErrors={fieldErrors} />
        <p className="text-xs text-slate-500">
          Obligatoire pour un rejet. Conservé dans le journal d&apos;audit.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={blocked || isSubmitting}
          onClick={() => submit("approved")}
          className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Approuver et publier
        </button>
        <button
          type="button"
          disabled={isSubmitting}
          onClick={() => submit("rejected")}
          className="rounded bg-red-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Rejeter
        </button>
        <button
          type="button"
          disabled={isSubmitting}
          onClick={() => submit("cancelled")}
          className="rounded border border-slate-300 px-4 py-2 text-sm"
        >
          Annuler la revue
        </button>
      </div>
    </form>
  );
}
