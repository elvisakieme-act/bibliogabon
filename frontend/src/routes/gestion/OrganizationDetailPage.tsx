import { useParams } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "@/api/client";
import type { StaffMembership } from "@/api/types";
import {
  grantsAccess,
  membershipRoleLabel,
  membershipStatusLabel,
  verificationStatusLabel
} from "@/components/staff/membershipLabels";
import { EmptyState } from "@/components/ui/EmptyState";
import { FieldErrors } from "@/components/ui/FieldErrors";
import { fieldErrorProps } from "@/components/ui/fieldErrors";
import { Skeleton } from "@/components/ui/Skeleton";
import { applyApiErrors, toFieldErrors } from "@/features/staff/applyApiErrors";
import {
  useAddOrganizationMember,
  useOrganizationMembers,
  useOrganizationQuotas,
  useOrganizationReport,
  useStaffOrganization,
  useSuspendOrganizationMember
} from "@/features/staff/hooks";

function firstOfThisMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function OrganizationDetailPage() {
  const { organizationId } = useParams({ from: "/gestion/organisations/$organizationId" });
  const id = Number(organizationId);
  const organization = useStaffOrganization(id);

  if (organization.isPending) {
    return <Skeleton label="Chargement de l'organisation" />;
  }
  if (organization.isError || !organization.data) {
    return (
      <EmptyState
        title="Organisation indisponible"
        description={
          organization.error instanceof ApiError
            ? organization.error.message
            : "Cette organisation n'a pas pu etre chargee."
        }
      />
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">{organization.data.name}</h2>
        {organization.data.requires_identity_verification ? (
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs text-amber-900">
            Vérification d&apos;identité exigée
          </span>
        ) : null}
      </header>

      <MembersSection organizationId={id} />
      <QuotasSection organizationId={id} />
      <ReportSection organizationId={id} />
    </div>
  );
}

function MembersSection({ organizationId }: { organizationId: number }) {
  const members = useOrganizationMembers(organizationId);
  const suspend = useSuspendOrganizationMember(organizationId);
  const [pending, setPending] = useState<StaffMembership | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  async function confirm() {
    if (!pending) return;
    setError("");
    if (!reason.trim()) {
      setError("Un motif est obligatoire : il est conservé au journal d'audit.");
      return;
    }
    try {
      await suspend.mutateAsync({ membershipId: pending.id, reason: reason.trim() });
      setPending(null);
      setReason("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "L'operation n'a pas pu aboutir.");
    }
  }

  return (
    <section className="space-y-4 rounded border border-slate-200 bg-white p-4">
      <h3 className="font-semibold">Membres</h3>

      {error ? (
        <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      ) : null}

      {members.isPending ? <Skeleton label="Chargement des membres" /> : null}
      {members.isError ? (
        <p className="text-sm text-slate-600">
          {members.error instanceof ApiError
            ? members.error.message
            : "Les membres n'ont pas pu etre charges."}
        </p>
      ) : null}

      {members.data ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">Membres de l&apos;organisation</caption>
            <thead className="bg-slate-50 text-left">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">
                  Personne
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Rôle
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Adhésion
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Identité
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {members.data.results.map((entry) => (
                <tr key={entry.id} className="border-t border-slate-100 align-top">
                  <th scope="row" className="px-3 py-2 text-left font-normal">
                    {entry.user.display_name}
                  </th>
                  <td className="px-3 py-2">{membershipRoleLabel(entry.role)}</td>
                  <td className="px-3 py-2">{membershipStatusLabel(entry.status)}</td>
                  <td className="px-3 py-2">
                    {verificationStatusLabel(entry.verification_status)}
                    {/* Sans cette phrase, un administrateur voyant une adhésion
                        « active » ne comprendra pas pourquoi le membre ne peut
                        pas lire, et conclura que la plateforme est cassée. */}
                    {!grantsAccess(entry.status, entry.verification_status) ? (
                      <span className="mt-1 block text-xs text-amber-900">
                        N&apos;accorde aucun accès en lecture
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">
                    {entry.status === "active" ? (
                      <button
                        type="button"
                        aria-label={`Suspendre ${entry.user.display_name}`}
                        className="rounded border border-slate-300 px-2 py-1 text-xs"
                        onClick={() => {
                          setPending(entry);
                          setReason("");
                          setError("");
                        }}
                      >
                        Suspendre
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {pending ? (
        <div className="space-y-3 rounded border border-orange-300 bg-orange-50 p-3">
          <h4 className="text-sm font-medium">Suspendre {pending.user.display_name}</h4>
          <p className="text-xs text-slate-700">
            L&apos;accès en lecture accordé par l&apos;organisation cesse immédiatement. Le
            compte, lui, reste intact.
          </p>
          <div className="flex flex-col gap-1">
            <label htmlFor="suspension-motif" className="text-sm font-medium">
              Motif
            </label>
            <textarea
              id="suspension-motif"
              rows={2}
              className="rounded border border-slate-300 px-2 py-1.5"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={confirm}
              disabled={suspend.isPending}
              className="rounded bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              Confirmer la suspension
            </button>
            <button
              type="button"
              onClick={() => setPending(null)}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            >
              Annuler
            </button>
          </div>
        </div>
      ) : null}

      <AddMemberForm organizationId={organizationId} />
    </section>
  );
}

interface AddMemberValues {
  email: string;
  role: string;
}

function AddMemberForm({ organizationId }: { organizationId: number }) {
  const add = useAddOrganizationMember(organizationId);
  const [formError, setFormError] = useState("");
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    reset,
    formState: { errors, isSubmitting }
  } = useForm<AddMemberValues>({ defaultValues: { email: "", role: "member" } });
  const fieldErrors = toFieldErrors(errors);

  const onSubmit = handleSubmit(async (values) => {
    clearErrors();
    setFormError("");
    try {
      await add.mutateAsync(values);
      reset({ email: "", role: "member" });
    } catch (caught) {
      setFormError(applyApiErrors(caught, { setError, fields: ["email", "role"] }));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-3 border-t border-slate-100 pt-4">
      <h4 className="text-sm font-medium">Rattacher un compte existant</h4>
      {formError ? (
        <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
          {formError}
        </p>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label htmlFor="membre-email" className="text-sm font-medium">
            Adresse du compte
          </label>
          <input
            id="membre-email"
            type="email"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("email")}
            {...fieldErrorProps("membre", "email", fieldErrors)}
          />
          <FieldErrors form="membre" field="email" fieldErrors={fieldErrors} />
          <p className="text-xs text-slate-500">
            La personne doit déjà avoir un compte : une organisation ne crée pas
            d&apos;identités.
          </p>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="membre-role" className="text-sm font-medium">
            Rôle
          </label>
          <select
            id="membre-role"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("role")}
          >
            <option value="member">Membre</option>
            <option value="admin">Administrateur</option>
          </select>
        </div>
      </div>
      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        Rattacher le membre
      </button>
    </form>
  );
}

function QuotasSection({ organizationId }: { organizationId: number }) {
  const quotas = useOrganizationQuotas(organizationId);

  return (
    <section className="space-y-3 rounded border border-slate-200 bg-white p-4">
      <h3 className="font-semibold">Quotas et contrats</h3>
      {quotas.isPending ? <Skeleton label="Chargement des quotas" /> : null}
      {quotas.data && quotas.data.results.length === 0 ? (
        <p className="text-sm text-slate-600">Aucun quota enregistré.</p>
      ) : null}
      {quotas.data && quotas.data.results.length > 0 ? (
        <ul className="divide-y divide-slate-100 text-sm">
          {quotas.data.results.map((quota) => (
            <li key={quota.id} className="py-2">
              <p className="font-medium">{quota.offer.name}</p>
              <p className="text-slate-600">
                {quota.seat_limit} sièges &middot; {quota.status}
              </p>
              {quota.contract_reference ? (
                <p className="text-slate-600">{quota.contract_reference}</p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function ReportSection({ organizationId }: { organizationId: number }) {
  const [period, setPeriod] = useState({ from: firstOfThisMonth(), to: today() });
  const report = useOrganizationReport(organizationId, period);

  const usage = (report.data?.metrics?.usage ?? {}) as Record<string, number>;
  const access = (report.data?.metrics?.access ?? {}) as Record<string, number>;

  return (
    <section className="space-y-3 rounded border border-slate-200 bg-white p-4">
      <h3 className="font-semibold">Rapport d&apos;usage</h3>
      <p className="text-sm text-slate-600">
        Agrégats uniquement. Le rapport ne dit jamais qui a lu quoi.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label htmlFor="rapport-debut" className="text-sm font-medium">
            Début
          </label>
          <input
            id="rapport-debut"
            type="date"
            className="rounded border border-slate-300 px-2 py-1.5"
            value={period.from}
            onChange={(event) => setPeriod((p) => ({ ...p, from: event.target.value }))}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="rapport-fin" className="text-sm font-medium">
            Fin
          </label>
          <input
            id="rapport-fin"
            type="date"
            className="rounded border border-slate-300 px-2 py-1.5"
            value={period.to}
            onChange={(event) => setPeriod((p) => ({ ...p, to: event.target.value }))}
          />
        </div>
      </div>

      {report.isPending ? <Skeleton label="Chargement du rapport" /> : null}
      {report.isError ? (
        <p role="alert" className="text-sm text-red-800">
          {report.error instanceof ApiError
            ? report.error.message
            : "Le rapport n'a pas pu etre genere."}
        </p>
      ) : null}
      {report.data ? (
        <dl className="grid gap-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-slate-500">Membres actifs</dt>
            <dd className="text-lg font-semibold">{access.active_member_count ?? 0}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Sessions de lecture</dt>
            <dd className="text-lg font-semibold">{usage.reader_session_count ?? 0}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Pages consultées</dt>
            <dd className="text-lg font-semibold">{usage.page_view_count ?? 0}</dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}
