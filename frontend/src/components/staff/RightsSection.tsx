import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import type { StaffDocument } from "@/api/types";
import {
  AGREEMENT_TYPE_OPTIONS,
  WITHDRAWAL_RULE_OPTIONS,
  authorizationStatusLabel
} from "@/components/staff/rightsOptions";
import { FieldErrors } from "@/components/ui/FieldErrors";
import { fieldErrorProps } from "@/components/ui/fieldErrors";
import { applyApiErrors, toFieldErrors } from "@/features/staff/applyApiErrors";
import { useDeclareDocumentRights } from "@/features/staff/hooks";

interface DeclarationValues {
  agreement_type: string;
  rights_holder_name: string;
  withdrawal_rule: string;
  revenue_sharing_rule: string;
  confidentiality_terms: string;
  consent_reference: string;
}

const FIELDS = [
  "agreement_type",
  "rights_holder_name",
  "withdrawal_rule",
  "revenue_sharing_rule",
  "confidentiality_terms",
  "consent_reference",
  "access_model"
] as const;

/**
 * Déclaration de droits, côté déposant.
 *
 * Cette section n'expose **aucune** commande d'approbation, et ce n'est pas
 * un oubli. L'approbation appartient au modérateur ; même désactivé, un
 * bouton « approuver » dirait au déposant qu'il peut la demander ici, et la
 * séparation des pouvoirs deviendrait une convention d'interface plutôt
 * qu'une règle. Le serveur, de son côté, n'expose pas les champs de décision
 * dans son sérialiseur de déclaration.
 */
export function RightsSection({
  document,
  documentId
}: {
  document: StaffDocument;
  documentId: number;
}) {
  const declare = useDeclareDocumentRights(documentId);
  const [formError, setFormError] = useState("");
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    reset,
    watch,
    formState: { errors, isSubmitting }
  } = useForm<DeclarationValues>({
    defaultValues: {
      agreement_type: document.rights?.agreement_type ?? "",
      rights_holder_name: document.rights?.rights_holder_name ?? "",
      withdrawal_rule: document.rights?.withdrawal_rule ?? "",
      revenue_sharing_rule: "",
      confidentiality_terms: "",
      consent_reference: ""
    }
  });
  const fieldErrors = toFieldErrors(errors);
  const agreementType = watch("agreement_type");

  useEffect(() => {
    reset({
      agreement_type: document.rights?.agreement_type ?? "",
      rights_holder_name: document.rights?.rights_holder_name ?? "",
      withdrawal_rule: document.rights?.withdrawal_rule ?? "",
      revenue_sharing_rule: "",
      confidentiality_terms: "",
      consent_reference: ""
    });
  }, [document, reset]);

  const onSubmit = handleSubmit(async (values) => {
    clearErrors();
    setFormError("");
    try {
      await declare.mutateAsync({
        ...values,
        // Le modele d'acces declare doit correspondre a celui du document :
        // autoriser une diffusion libre puis vendre le document par
        // abonnement est la faute que la regle serveur empeche. L'ecran le
        // reprend du document plutot que de le redemander, pour qu'on ne
        // puisse pas la commettre par inadvertance.
        access_model: document.access_model
      });
    } catch (caught) {
      setFormError(applyApiErrors(caught, { setError, fields: FIELDS }));
    }
  });

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="space-y-5 rounded-[calc(var(--radius)+0.25rem)] border border-[var(--border)] bg-[var(--card)] p-5 shadow-editorial"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-lg text-[var(--navy)]">Déclaration de droits</h3>
        {document.rights ? (
          <span className="rounded-full bg-[var(--navy-soft)] px-3 py-1 text-xs font-semibold text-[var(--navy)]">
            {authorizationStatusLabel(document.rights.authorization_status)}
          </span>
        ) : null}
      </div>
      <p className="text-sm text-[var(--muted-foreground)]">
        Vous declarez. Un moderateur decide ensuite, au vu du contrat ou de l&apos;autorisation
        signee. Toute modification de la déclaration la remet en attente de revue.
      </p>

      {formError ? (
        <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
          {formError}
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label htmlFor="droits-type" className="text-sm font-semibold text-[var(--navy)]">
            Type d&apos;accord
          </label>
          <select
            id="droits-type"
            className="w-full rounded-[var(--radius)] border border-[var(--border)] bg-white px-3.5 py-2.5 text-[15px] transition focus-visible:border-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
            {...register("agreement_type", {
              required: "Choisissez le type d'accord qui couvre ce document."
            })}
            {...fieldErrorProps("droits", "agreement_type", fieldErrors)}
          >
            <option value="">Choisir</option>
            {AGREEMENT_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <FieldErrors form="droits" field="agreement_type" fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="droits-titulaire"
            className="text-sm font-semibold text-[var(--navy)]"
          >
            Titulaire des droits
          </label>
          <input
            id="droits-titulaire"
            className="w-full rounded-[var(--radius)] border border-[var(--border)] bg-white px-3.5 py-2.5 text-[15px] transition focus-visible:border-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
            {...register("rights_holder_name", {
              required: "Le nom du titulaire des droits est obligatoire."
            })}
            {...fieldErrorProps("droits", "rights_holder_name", fieldErrors)}
          />
          <FieldErrors form="droits" field="rights_holder_name" fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="droits-retrait" className="text-sm font-semibold text-[var(--navy)]">
            Règle de retrait
          </label>
          <select
            id="droits-retrait"
            className="w-full rounded-[var(--radius)] border border-[var(--border)] bg-white px-3.5 py-2.5 text-[15px] transition focus-visible:border-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
            {...register("withdrawal_rule", {
              required: "Choisissez la règle de retrait applicable."
            })}
            {...fieldErrorProps("droits", "withdrawal_rule", fieldErrors)}
          >
            <option value="">Choisir</option>
            {WITHDRAWAL_RULE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <FieldErrors form="droits" field="withdrawal_rule" fieldErrors={fieldErrors} />
        </div>

        {document.category === "student_work" ? (
          <div className="flex flex-col gap-1">
            <label
              htmlFor="droits-consentement"
              className="text-sm font-semibold text-[var(--navy)]"
            >
              Référence du consentement
            </label>
            <input
              id="droits-consentement"
              className="w-full rounded-[var(--radius)] border border-[var(--border)] bg-white px-3.5 py-2.5 text-[15px] transition focus-visible:border-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
              {...register("consent_reference")}
              {...fieldErrorProps("droits", "consent_reference", fieldErrors)}
            />
            <FieldErrors form="droits" field="consent_reference" fieldErrors={fieldErrors} />
            <p className="text-xs text-[var(--muted-foreground)]">
              Un travail d&apos;etudiant exige un consentement explicite.
            </p>
          </div>
        ) : null}

        {agreementType === "commercial_distribution" ? (
          <div className="flex flex-col gap-1">
            <label
              htmlFor="droits-partage"
              className="text-sm font-semibold text-[var(--navy)]"
            >
              Règle de partage des revenus
            </label>
            <input
              id="droits-partage"
              className="w-full rounded-[var(--radius)] border border-[var(--border)] bg-white px-3.5 py-2.5 text-[15px] transition focus-visible:border-[var(--gold)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)]"
              {...register("revenue_sharing_rule")}
              {...fieldErrorProps("droits", "revenue_sharing_rule", fieldErrors)}
            />
            <FieldErrors form="droits" field="revenue_sharing_rule" fieldErrors={fieldErrors} />
          </div>
        ) : null}
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="inline-flex items-center justify-center rounded-[var(--radius)] bg-[var(--navy)] px-4 py-2.5 text-sm font-semibold text-white shadow-editorial transition hover:bg-[var(--navy-deep)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gold)] focus-visible:ring-offset-2 disabled:opacity-45"
      >
        Enregistrer la déclaration
      </button>
    </form>
  );
}
