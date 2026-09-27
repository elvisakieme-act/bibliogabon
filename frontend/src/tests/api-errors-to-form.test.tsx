import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";

import { ApiError } from "@/api/client";
import { FieldErrors } from "@/components/ui/FieldErrors";
import { fieldErrorProps } from "@/components/ui/fieldErrors";
import { applyApiErrors, toFieldErrors } from "@/features/staff/applyApiErrors";

interface DemoValues {
  title: string;
  slug: string;
}

const FIELDS = ["title", "slug"] as const;

/** Formulaire jetable : on teste le pont, pas un ecran particulier. */
function DemoForm({ refusal }: { refusal: unknown }) {
  const [formError, setFormError] = useState("");
  const [submits, setSubmits] = useState(0);
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    formState: { errors }
  } = useForm<DemoValues>({ defaultValues: { title: "", slug: "" } });
  const fieldErrors = toFieldErrors(errors);

  const onSubmit = handleSubmit(() => {
    clearErrors();
    setSubmits((count) => count + 1);
    // Le second envoi reussit : on verifie que le refus precedent disparait.
    if (submits > 0) {
      setFormError("");
      return;
    }
    setFormError(applyApiErrors(refusal, { setError, fields: FIELDS }));
  });

  return (
    <form onSubmit={onSubmit} noValidate>
      {formError ? <p role="alert">{formError}</p> : null}
      <label htmlFor="demo-title">Titre</label>
      <input
        id="demo-title"
        {...register("title")}
        {...fieldErrorProps("demo", "title", fieldErrors)}
      />
      <FieldErrors form="demo" field="title" fieldErrors={fieldErrors} />
      <label htmlFor="demo-slug">Identifiant</label>
      <input
        id="demo-slug"
        {...register("slug")}
        {...fieldErrorProps("demo", "slug", fieldErrors)}
      />
      <FieldErrors form="demo" field="slug" fieldErrors={fieldErrors} />
      <button type="submit">Enregistrer</button>
    </form>
  );
}

function envelope(fieldErrors: Record<string, string[]>, message = "Document invalide.") {
  return new ApiError(400, "invalid_request", message, fieldErrors);
}

async function submit() {
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
}

describe("report des refus serveur sur les champs", () => {
  it("place chaque erreur nommee sur son champ", async () => {
    render(
      <DemoForm
        refusal={envelope({
          title: ["Ce champ est obligatoire."],
          slug: ["Cet identifiant est deja pris."]
        })}
      />
    );

    await submit();

    expect(await screen.findByText("Ce champ est obligatoire.")).toBeInTheDocument();
    expect(screen.getByText("Cet identifiant est deja pris.")).toBeInTheDocument();
  });

  it("associe le message a son input et deplace le focus sur le premier en erreur", async () => {
    // Sans aria-invalid ni aria-describedby, l'erreur n'existe que
    // visuellement : un lecteur d'ecran annonce le message sans dire quel
    // champ est en cause.
    render(<DemoForm refusal={envelope({ slug: ["Identifiant invalide."] })} />);

    await submit();

    const input = await screen.findByLabelText("Identifiant");
    expect(input).toHaveAttribute("aria-invalid", "true");
    const describedBy = input.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy as string)).toHaveTextContent(
      "Identifiant invalide."
    );
    await waitFor(() => expect(input).toHaveFocus());
  });

  it("ne perd pas une erreur portant sur un champ que le formulaire ne possede pas", async () => {
    // `setError` sur un champ inconnu n'affiche rien : le refus serait
    // silencieusement avale et l'utilisateur verrait un echec sans raison.
    render(
      <DemoForm
        refusal={envelope({ academic_domain: ["Domaine inconnu."], title: ["Trop court."] })}
      />
    );

    await submit();

    expect(await screen.findByText("Trop court.")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Domaine inconnu.");
  });

  it("rend un message de formulaire quand le serveur n'attribue aucun champ", async () => {
    render(
      <DemoForm refusal={new ApiError(409, "document_locked", "Ce document est verrouille.")} />
    );

    await submit();

    expect(await screen.findByRole("alert")).toHaveTextContent("Ce document est verrouille.");
  });

  it("ne laisse pas fuir le texte d'une exception inattendue", async () => {
    render(<DemoForm refusal={new TypeError("cannot read properties of undefined")} />);

    await submit();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/inattendue/i);
    expect(alert).not.toHaveTextContent(/undefined/);
  });

  it("efface le refus precedent au nouvel envoi", async () => {
    render(<DemoForm refusal={envelope({ title: ["Ce champ est obligatoire."] })} />);
    await submit();
    expect(await screen.findByText("Ce champ est obligatoire.")).toBeInTheDocument();

    await submit();

    await waitFor(() => {
      expect(screen.queryByText("Ce champ est obligatoire.")).not.toBeInTheDocument();
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
