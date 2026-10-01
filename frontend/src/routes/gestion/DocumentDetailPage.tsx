import { useQueryClient } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/useAuth";
import { isContentAdmin } from "@/auth/roles";
import type { StaffDocument } from "@/api/types";
import { AuditTrail } from "@/components/staff/AuditTrail";
import { AuthorsSection } from "@/components/staff/AuthorsSection";
import { CompletenessChecklist } from "@/components/staff/CompletenessChecklist";
import { DocumentStateBadge } from "@/components/staff/DocumentStateBadge";
import { IngestionStatus } from "@/components/staff/IngestionStatus";
import { LifecycleActions } from "@/components/staff/LifecycleActions";
import { ACCESS_MODEL_OPTIONS, CATEGORY_OPTIONS } from "@/components/staff/options";
import { RightsSection } from "@/components/staff/RightsSection";
import { SourceUpload } from "@/components/staff/SourceUpload";
import { EmptyState } from "@/components/ui/EmptyState";
import { fieldErrorProps } from "@/components/ui/fieldErrors";
import {
  ActionButton,
  Field,
  FormAlert,
  FormNotice,
  Panel,
  Select,
  TextArea,
  TextInput
} from "@/components/ui/form";
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
            : "Ce document n'a pas pu être charge."
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
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const missing = document.missing_for_submission;

  return (
    <div className="max-w-3xl space-y-6">
      <header className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] pb-4">
        <h2 className="font-display text-2xl text-[var(--navy)]">{document.title}</h2>
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

      <LifecycleActions document={document} documentId={documentId} />

      {/* Le journal est réservé à la modération côté serveur. L'afficher à un
          déposant ne lui montrerait rien et ferait échouer une requête à
          chaque rendu. */}
      {isContentAdmin(user?.account_type) ? <AuditTrail documentId={documentId} /> : null}

      <Panel
        title="Soumission"
        description={
          missing.length > 0
            ? "La soumission s'ouvrira quand la liste ci-dessus sera vide."
            : "Tout est réuni : la modération pourra examiner ce dépôt."
        }
      >
        <ActionButton
          // La barrière vient du serveur, qui la recalcule : le bouton ne fait
          // que refléter `missing_for_submission`, il ne la décide pas.
          disabled={missing.length > 0 || submit.isPending}
          onClick={() => submit.mutate()}
        >
          Soumettre à la revue
        </ActionButton>
      </Panel>
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
    <form onSubmit={onSubmit} noValidate>
      <Panel
        title="Métadonnées"
        description="Ce que le catalogue affichera. Le domaine et le type conditionnent la soumission."
      >
        {formError ? <FormAlert>{formError}</FormAlert> : null}
        {saved ? <FormNotice>Métadonnées enregistrées.</FormNotice> : null}

        <Field
          id="meta-titre"
          label="Titre"
          required
          form="meta"
          name="title"
          errors={fieldErrors}
        >
          <TextInput
            id="meta-titre"
            invalid={Boolean(fieldErrors.title?.length)}
            {...register("title")}
            {...fieldErrorProps("meta", "title", fieldErrors)}
          />
        </Field>

        <Field
          id="meta-resume"
          label="Résumé"
          hint="Quelques lignes : c'est ce qu'un lecteur lit avant d'ouvrir le document."
          form="meta"
          name="abstract"
          errors={fieldErrors}
        >
          <TextArea
            id="meta-resume"
            rows={4}
            invalid={Boolean(fieldErrors.abstract?.length)}
            {...register("abstract")}
            {...fieldErrorProps("meta", "abstract", fieldErrors)}
          />
        </Field>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field
            id="meta-domaine"
            label="Domaine académique"
            form="meta"
            name="academic_domain"
            errors={fieldErrors}
          >
            <Select
              id="meta-domaine"
              invalid={Boolean(fieldErrors.academic_domain?.length)}
              {...register("academic_domain")}
              {...fieldErrorProps("meta", "academic_domain", fieldErrors)}
            >
              <option value="">Non renseigné</option>
              {(domains.data?.results ?? []).map((domain) => (
                <option key={domain.id} value={String(domain.id)}>
                  {domain.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            id="meta-type"
            label="Type de document"
            form="meta"
            name="document_type"
            errors={fieldErrors}
          >
            <Select
              id="meta-type"
              invalid={Boolean(fieldErrors.document_type?.length)}
              {...register("document_type")}
              {...fieldErrorProps("meta", "document_type", fieldErrors)}
            >
              <option value="">Non renseigné</option>
              {(types.data?.results ?? []).map((type) => (
                <option key={type.id} value={String(type.id)}>
                  {type.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            id="meta-categorie"
            label="Catégorie de contenu"
            required
            form="meta"
            name="category"
            errors={fieldErrors}
          >
            <Select
              id="meta-categorie"
              invalid={Boolean(fieldErrors.category?.length)}
              {...register("category")}
              {...fieldErrorProps("meta", "category", fieldErrors)}
            >
              {CATEGORY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            id="meta-acces"
            label="Modèle d'accès"
            required
            form="meta"
            name="access_model"
            errors={fieldErrors}
          >
            <Select
              id="meta-acces"
              invalid={Boolean(fieldErrors.access_model?.length)}
              {...register("access_model")}
              {...fieldErrorProps("meta", "access_model", fieldErrors)}
            >
              {ACCESS_MODEL_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            id="meta-langue"
            label="Langue"
            form="meta"
            name="language_code"
            errors={fieldErrors}
          >
            <TextInput
              id="meta-langue"
              invalid={Boolean(fieldErrors.language_code?.length)}
              {...register("language_code")}
              {...fieldErrorProps("meta", "language_code", fieldErrors)}
            />
          </Field>

          <Field
            id="meta-annee"
            label="Année de publication"
            form="meta"
            name="publication_year"
            errors={fieldErrors}
          >
            <TextInput
              id="meta-annee"
              inputMode="numeric"
              invalid={Boolean(fieldErrors.publication_year?.length)}
              {...register("publication_year")}
              {...fieldErrorProps("meta", "publication_year", fieldErrors)}
            />
          </Field>
        </div>

        <div className="mt-5">
          <ActionButton type="submit" disabled={isSubmitting}>
            Enregistrer les métadonnées
          </ActionButton>
        </div>
      </Panel>
    </form>
  );
}
