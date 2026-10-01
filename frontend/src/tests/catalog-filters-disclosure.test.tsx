import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { RouterProvider, createMemoryHistory } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/router";

/**
 * Le panneau de filtres du catalogue.
 *
 * Déployé partout, il occupait tout le premier écran d'un téléphone : on
 * arrivait sur un catalogue sans voir un seul document, c'est-à-dire sur un
 * formulaire. Il se replie donc en dessous de la colonne qui lui est destinée.
 *
 * Ce que jsdom peut en dire est l'état d'ouverture, pas l'apparence : il
 * n'applique aucune feuille de style, pas même celle du navigateur — c'est
 * d'ailleurs pourquoi la première tentative, qui jouait sur une classe, a passé
 * les tests en laissant le panneau vide sur grand écran.
 */
function ecran(large: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: large && query.includes("min-width"),
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false
  }));
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({
    history: createMemoryHistory({ initialEntries: ["/catalogue"] })
  });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }))
    )
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("filtres du catalogue", () => {
  it("se replie sur un écran étroit", async () => {
    ecran(false);
    afficher();

    const panneau = await screen.findByText("Affiner la recherche");
    expect(panneau.closest("details")).not.toHaveAttribute("open");
  });

  it("s'ouvre dès que la grille lui offre une colonne", async () => {
    ecran(true);
    afficher();

    const panneau = await screen.findByText("Affiner la recherche");
    expect(panneau.closest("details")).toHaveAttribute("open");
  });
});
