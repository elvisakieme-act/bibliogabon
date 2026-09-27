import { useQueryClient } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "@/api/client";
import type { StaffDocument } from "@/api/types";
import { AuthorsSection } from "@/components/staff/AuthorsSection";
import { CompletenessChecklist } from "@/components/staff/CompletenessChecklist";
import { DocumentStateBadge } from "@/components/staff/DocumentStateBadge";
import { IngestionStatus } from "@/components/staff/IngestionStatus";
import { ACCESS_MODEL_OPTIONS, CATEGORY_OPTIONS } from "@/components/staff/options";
import { RightsSection } from "@/components/staff/RightsSection";
import { SourceUpload } from "@/components/staff/SourceUpload";
import { EmptyState } from "@/components/ui/EmptyState";
import { FieldErrors } from "@/components/ui/FieldErrors";
import { fieldErrorProps } from "@/components/ui/fieldErrors";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDocumentTypes, useDomains } from "@/features/catalog/hooks";
import { applyApiErrors, toFieldErrors } from "@/features/staff/applyApiErrors";
import {
  useStaffDocument,
  useStaffIndex,
  useSubmitStaffDocument,
  useUpdateStaffDocument
} from "@/features/staff/hooks";

export function DocumentDetailPage() {
  const { documentId } = useParams({ from: "/gestion/documents/$documentId" });
  const id = Number(documentId);
  const query = useStaffDocument(id);

  if (query.isPending) {
    return <Skeleton label="Chargement du document" />;
  }
  if (query.isError || !query.data) {
    return (
      <EmptyState
        title="Document indisponible"
        description={
          query.error instanceof ApiError
            ? query.error.message
            : "Ce document n'a pas pu etre charge."
        }
      />
    );
  }

  return <DocumentDetail document={query.data} documentId={id} />;
}

function DocumentDetail({
  document,
  documentId
}: {
  document: StaffDocument;
  documentId: number;
}) {
  const submit = useSubmitStaffDocument(documentId);
  const index = useStaffIndex();
  const queryClient = useQueryClient();
  const missing = document.missing_for_submission;

  return (
    <div className="max-w-3xl space-y-6">
      <header className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">{document.title}</h2>
        <DocumentStateBadge status={document.publication_status} />
      </header>

      <CompletenessChecklist codes={missing} />

      <MetadataSection document={document} documentId={documentId} />

      <AuthorsSection document={document} documentId={documentId} />

      <RightsSection document={document} documentId={documentId} />

      {index.data?.upload?.max_bytes ? (
        <SourceUpload
          documentId={documentId}
          maxBytes={index.data.upload.max_bytes}
          acceptedMimeTypes={index.data.upload.accepted_mime_types ?? []}
          onUploaded={() => {
            // Le suivi doit repartir sur l'etat du nouveau depot, pas sur
            // celui du precedent.
            queryClient.invalidateQueries({ queryKey: ["staff", "ingestion", documentId] });
            queryClient.invalidateQueries({ queryKey: ["staff", "document", documentId] });
          }}
        />
      ) : null}

      <IngestionStatus documentId={documentId} />

      <section className="space-y-2">
        <button
          type="button"
          // La barriere vient du serveur, qui la recalcule : le bouton ne
          // fait que refleter `missing_for_submission`, il ne la decide pas.
          disabled={missing.length > 0 || submit.isPending}
          onClick={() => submit.mutate()}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Soumettre a la revue
        </button>
        {missing.length > 0 ? (
          <p className="text-sm text-slate-600">
            La soumission s&apos;ouvrira quand la liste ci-dessus sera vide.
          </p>
        ) : null}
      </section>
    </div>
  );
}

interface MetadataValues {
  title: string;
  abstract: string;
  language_code: string;
  publication_year: string;
  academic_domain: string;
  document_type: string;
  category: string;
  access_model: string;
}

const METADATA_FIELDS = [
  "title",
  "abstract",
  "language_code",
  "publication_year",
  "academic_domain",
  "document_type",
  "category",
  "access_model"
] as const;

function MetadataSection({
  document,
  documentId
}: {
  document: StaffDocument;
  documentId: number;
}) {
  const update = useUpdateStaffDocument(documentId);
  const domains = useDomains();
  const types = useDocumentTypes();
  const [formError, setFormError] = useState("");
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    reset,
    formState: { errors, isSubmitting }
  } = useForm<MetadataValues>({
    defaultValues: {
      title: document.title,
      abstract: document.abstract,
      language_code: document.language_code,
      publication_year: document.publication_year ? String(document.publication_year) : "",
      academic_domain: document.academic_domain ? String(document.academic_domain.id) : "",
      document_type: document.document_type ? String(document.document_type.id) : "",
      category: document.category,
      access_model: document.access_model
    }
  });
  const fieldErrors = toFieldErrors(errors);

  // Le serveur normalise ce qu'il enregistre. Reafficher sa reponse plutot
  // que ce qui a ete tape evite qu'un ecran affiche un etat que la base
  // n'a pas.
  useEffect(() => {
    reset({
      title: document.title,
      abstract: document.abstract,
      language_code: document.language_code,
      publication_year: document.publication_year ? String(document.publication_year) : "",
      academic_domain: document.academic_domain ? String(document.academic_domain.id) : "",
      document_type: document.document_type ? String(document.document_type.id) : "",
      category: document.category,
      access_model: document.access_model
    });
  }, [document, reset]);

  const onSubmit = handleSubmit(async (values) => {
    clearErrors();
    setFormError("");
    setSaved(false);
    try {
      await update.mutateAsync({
        title: values.title,
        abstract: values.abstract,
        language_code: values.language_code,
        publication_year: values.publication_year ? Number(values.publication_year) : null,
        // Des identifiants numeriques, pas des slugs : les filtres de la
        // liste prennent des slugs, l'ecriture prend des cles primaires.
        academic_domain: values.academic_domain ? Number(values.academic_domain) : null,
        document_type: values.document_type ? Number(values.document_type) : null,
        category: values.category,
        access_model: values.access_model
      });
      setSaved(true);
    } catch (caught) {
      setFormError(applyApiErrors(caught, { setError, fields: METADATA_FIELDS }));
    }
  });

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="space-y-4 rounded border border-slate-200 bg-white p-4"
    >
      <h3 className="font-semibold">Metadonnees</h3>
      {formError ? (
        <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
          {formError}
        </p>
      ) : null}
      {saved ? (
        <p role="status" className="text-sm text-emerald-700">
          Metadonnees enregistrees.
        </p>
      ) : null}

      <div className="flex flex-col gap-1">
        <label htmlFor="meta-titre" className="text-sm font-medium">
          Titre
        </label>
        <input
          id="meta-titre"
          className="rounded border border-slate-300 px-2 py-1.5"
          {...register("title")}
          {...fieldErrorProps("meta", "title", fieldErrors)}
        />
        <FieldErrors form="meta" field="title" fieldErrors={fieldErrors} />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="meta-resume" className="text-sm font-medium">
          Resume
        </label>
        <textarea
          id="meta-resume"
          rows={4}
          className="rounded border border-slate-300 px-2 py-1.5"
          {...register("abstract")}
          {...fieldErrorProps("meta", "abstract", fieldErrors)}
        />
        <FieldErrors form="meta" field="abstract" fieldErrors={fieldErrors} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label htmlFor="meta-domaine" className="text-sm font-medium">
            Domaine academique
          </label>
          <select
            id="meta-domaine"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("academic_domain")}
            {...fieldErrorProps("meta", "academic_domain", fieldErrors)}
          >
            <option value="">Non renseigne</option>
            {(domains.data?.results ?? []).map((domain) => (
              <option key={domain.id} value={String(domain.id)}>
                {domain.name}
              </option>
            ))}
          </select>
          <FieldErrors form="meta" field="academic_domain" fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="meta-type" className="text-sm font-medium">
            Type de document
          </label>
          <select
            id="meta-type"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("document_type")}
            {...fieldErrorProps("meta", "document_type", fieldErrors)}
          >
            <option value="">Non renseigne</option>
            {(types.data?.results ?? []).map((type) => (
              <option key={type.id} value={String(type.id)}>
                {type.name}
              </option>
            ))}
          </select>
          <FieldErrors form="meta" field="document_type" fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="meta-categorie" className="text-sm font-medium">
            Categorie de contenu
          </label>
          <select
            id="meta-categorie"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("category")}
            {...fieldErrorProps("meta", "category", fieldErrors)}
          >
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <FieldErrors form="meta" field="category" fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="meta-acces" className="text-sm font-medium">
            Modele d&apos;acces
          </label>
          <select
            id="meta-acces"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("access_model")}
            {...fieldErrorProps("meta", "access_model", fieldErrors)}
          >
            {ACCESS_MODEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <FieldErrors form="meta" field="access_model" fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="meta-langue" className="text-sm font-medium">
            Langue
          </label>
          <input
            id="meta-langue"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("language_code")}
            {...fieldErrorProps("meta", "language_code", fieldErrors)}
          />
          <FieldErrors form="meta" field="language_code" fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="meta-annee" className="text-sm font-medium">
            Annee de publication
          </label>
          <input
            id="meta-annee"
            inputMode="numeric"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("publication_year")}
            {...fieldErrorProps("meta", "publication_year", fieldErrors)}
          />
          <FieldErrors form="meta" field="publication_year" fieldErrors={fieldErrors} />
        </div>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        Enregistrer les metadonnees
      </button>
    </form>
  );
}
