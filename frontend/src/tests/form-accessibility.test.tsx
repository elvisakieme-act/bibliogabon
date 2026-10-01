import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/router";

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({
    history: createMemoryHistory({ initialEntries: [path] })
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

function refuseWithFieldErrors(fieldErrors: Record<string, string[]>) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "invalid_request",
            message: "Requête invalide.",
            field_errors: fieldErrors
          }
        }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      )
    )
  );
}

describe("page d'inscription", () => {
  it("dit ce qu'un compte apporte, sur un grand écran comme sur un téléphone", async () => {
    // On demandait trois champs sans dire ce qu'on y gagne — alors que la
    // lecture libre, elle, n'en demande aucun. Les raisons vivaient dans un
    // panneau masqué sous `lg`, c'est-à-dire absent là où se trouvent la
    // plupart des lecteurs : elles sont donc écrites deux fois, et les deux
    // doivent rester.
    vi.stubGlobal("fetch", vi.fn());
    renderAt("/inscription");
    await screen.findByRole("button", { name: /Créer mon compte/i });

    expect(screen.getAllByText(/Reprendre une lecture là où vous l'avez laissée/)).toHaveLength(
      2
    );
    expect(screen.getAllByText(/rattachement vérifié/)).toHaveLength(2);
    // Et l'on ne laisse pas croire qu'un compte est nécessaire pour lire.
    expect(screen.getByText(/ne demande aucun compte/)).toBeInTheDocument();
  });
});

describe("accessibilité des erreurs de formulaire", () => {
  it("associe une erreur de champ à son input à l'inscription", async () => {
    refuseWithFieldErrors({ email: ["Cette adresse est déjà utilisée."] });
    renderAt("/inscription");
    // La route se resout de facon asynchrone : sans cette attente, on
    // interroge un arbre encore vide.
    await screen.findByRole("button", { name: /Créer mon compte/i });

    await userEvent.type(screen.getByLabelText(/Nom affiché/i), "Prof X");
    await userEvent.type(screen.getByLabelText(/Email/i), "deja@example.ga");
    await userEvent.type(screen.getByLabelText(/Mot de passe/i), "passphrase");
    await userEvent.click(screen.getByRole("button", { name: /Créer mon compte/i }));

    const input = await screen.findByLabelText(/Email/i);
    await waitFor(() => expect(input).toHaveAttribute("aria-invalid", "true"));
    const described = input.getAttribute("aria-describedby");
    expect(described).toBeTruthy();
    expect(document.getElementById(described!)).toHaveTextContent(
      "Cette adresse est déjà utilisée."
    );
  });

  it("associe une erreur de champ à son input à la connexion", async () => {
    refuseWithFieldErrors({ email: ["Compte inconnu."] });
    renderAt("/connexion");
    await screen.findByRole("button", { name: /Se connecter/i });

    await userEvent.type(screen.getByLabelText(/Email/i), "inconnu@example.ga");
    await userEvent.type(screen.getByLabelText(/Mot de passe/i), "x");
    await userEvent.click(screen.getByRole("button", { name: /Se connecter/i }));

    const input = await screen.findByLabelText(/Email/i);
    await waitFor(() => expect(input).toHaveAttribute("aria-invalid", "true"));
    const described = input.getAttribute("aria-describedby");
    expect(document.getElementById(described!)).toHaveTextContent("Compte inconnu.");
  });

  it("laisse les champs valides sans aria-invalid", async () => {
    refuseWithFieldErrors({ email: ["Compte inconnu."] });
    renderAt("/connexion");
    await screen.findByRole("button", { name: /Se connecter/i });

    await userEvent.type(screen.getByLabelText(/Email/i), "a@b.ga");
    await userEvent.type(screen.getByLabelText(/Mot de passe/i), "x");
    await userEvent.click(screen.getByRole("button", { name: /Se connecter/i }));

    await waitFor(() =>
      expect(screen.getByLabelText(/Email/i)).toHaveAttribute("aria-invalid", "true")
    );
    expect(screen.getByLabelText(/Mot de passe/i)).not.toHaveAttribute("aria-invalid", "true");
  });
});
