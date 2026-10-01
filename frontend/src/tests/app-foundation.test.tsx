import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { createAppRouter } from "@/router";

afterEach(cleanup);

function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  const router = createAppRouter({
    history: createMemoryHistory({ initialEntries: [path] })
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

describe("app foundation", () => {
  it("renders the discovery home route", async () => {
    renderAt("/");

    // Le titre de l'accueil dit ce qu'on peut faire, pas comment la
    // plateforme s'appelle. Le nom figure déjà dans la barre de navigation,
    // deux centimètres plus haut : le répéter en `h1` dépensait l'espace le
    // plus précieux du produit à redire son étiquette.
    const titre = await screen.findByRole("heading", { level: 1 });
    expect(titre).toHaveTextContent(/thèses/i);
    expect(titre).not.toHaveTextContent(/^BiblioGABON$/);

    // La recherche est l'action principale : un étudiant arrive en cherchant
    // quelque chose, pas pour être convaincu.
    expect(screen.getByRole("search")).toBeInTheDocument();
  });

  it("n'affiche pas le volume du catalogue tant qu'il ne plaide pas", async () => {
    // L'accueil annonçait « 6 documents dans le catalogue ». Un chiffre de
    // cette taille ne rassure pas : il dit au visiteur que la bibliothèque
    // est vide, ce qui est pire que de ne rien dire. Le volume reviendra
    // quand il plaidera ; d'ici là, ce sont les documents eux-mêmes qui
    // tiennent lieu de preuve.
    renderAt("/");
    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByText(/documents dans le catalogue/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/domaines académiques/i)).not.toBeInTheDocument();
  });

  it("renders the route-level not-found state for unknown URLs", async () => {
    renderAt("/adresse-inconnue");

    expect(
      await screen.findByRole("heading", { name: "Page introuvable" })
    ).toBeInTheDocument();
  });
});
