import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import type { StaffDocument } from "@/api/types";
import { ACCESS_MODEL_OPTIONS, CATEGORY_OPTIONS } from "@/components/staff/options";
import { FieldErrors } from "@/components/ui/FieldErrors";
import { fieldErrorProps } from "@/components/ui/fieldErrors";
import { applyApiErrors, toFieldErrors } from "@/features/staff/applyApiErrors";
import { useCreateStaffDocument } from "@/features/staff/hooks";

interface DraftValues {
  title: string;
  slug: string;
  category: string;
  access_model: string;
}

const FIELDS = ["title", "slug", "category", "access_model"] as const;

export function DocumentCreatePage() {
  const navigate = useNavigate();
  const create = useCreateStaffDocument();
  const [formError, setFormError] = useState("");
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    formState: { errors, isSubmitting }
  } = useForm<DraftValues>({
    defaultValues: { title: "", slug: "", category: "", access_model: "" }
  });
  const fieldErrors = toFieldErrors(errors);

  // Le minimum que le serveur exige, et rien de plus : le reste se remplit
  // sur la fiche, section par section, pour qu'un enseignant puisse
  // enregistrer tot et revenir.
  const onSubmit = handleSubmit(async (values) => {
    clearErrors();
    setFormError("");
    try {
      const document = (await create.mutateAsync(values)) as StaffDocument;
      await navigate({
        to: "/gestion/documents/$documentId",
        params: { documentId: String(document.id) }
      });
    } catch (caught) {
      setFormError(applyApiErrors(caught, { setError, fields: FIELDS }));
    }
  });

  return (
    <section className="max-w-2xl space-y-4">
      <h2 className="text-xl font-semibold">Nouveau document</h2>
      <p className="text-sm text-slate-600">
        Le brouillon demande le minimum. Metadonnees, auteurs, droits et fichier se remplissent
        ensuite sur sa fiche.
      </p>

      <form
        onSubmit={onSubmit}
        noValidate
        className="space-y-4 rounded border border-slate-200 bg-white p-4"
      >
        {formError ? (
          <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
            {formError}
          </p>
        ) : null}

        <div className="flex flex-col gap-1">
          <label htmlFor="creation-titre" className="text-sm font-medium">
            Titre
          </label>
          <input
            id="creation-titre"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("title", { required: "Un titre est obligatoire." })}
            {...fieldErrorProps("creation", "title", fieldErrors)}
          />
          <FieldErrors form="creation" field="title" fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="creation-slug" className="text-sm font-medium">
            Identifiant d&apos;adresse
          </label>
          <input
            id="creation-slug"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("slug", { required: "Un identifiant est obligatoire." })}
            {...fieldErrorProps("creation", "slug", fieldErrors)}
          />
          <FieldErrors form="creation" field="slug" fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="creation-categorie" className="text-sm font-medium">
            Catégorie de contenu
          </label>
          <select
            id="creation-categorie"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("category", { required: "Une catégorie est obligatoire." })}
            {...fieldErrorProps("creation", "category", fieldErrors)}
          >
            <option value="">Choisir</option>
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <FieldErrors form="creation" field="category" fieldErrors={fieldErrors} />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="creation-acces" className="text-sm font-medium">
            Modèle d&apos;accès
          </label>
          <select
            id="creation-acces"
            className="rounded border border-slate-300 px-2 py-1.5"
            {...register("access_model", { required: "Un modèle d'accès est obligatoire." })}
            {...fieldErrorProps("creation", "access_model", fieldErrors)}
          >
            <option value="">Choisir</option>
            {ACCESS_MODEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <FieldErrors form="creation" field="access_model" fieldErrors={fieldErrors} />
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Créer le brouillon
        </button>
      </form>
    </section>
  );
}
