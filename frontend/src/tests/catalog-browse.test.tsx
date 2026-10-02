import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryHistory } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/router";

/**
 * Parcourir le catalogue.
 *
 * Son point d'entrée n'acceptait aucun paramètre : le panneau de filtres de
 * l'écran renvoyait vers la recherche, si bien qu'on croyait affiner une liste
 * et qu'on changeait de page. Ces tests tiennent les deux bouts — ce que
 * l'écran demande au serveur, et ce qu'il dit quand rien ne correspond.
 */
let fetchMock: ReturnType<typeof vi.fn>;

function reponseVide() {
  return new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }), {
    status: 200
  });
}

function afficher(adresse: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({
    history: createMemoryHistory({ initialEntries: [adresse] })
  });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

function adressesDemandees() {
  return fetchMock.mock.calls.map(([url]) => String(url));
}

beforeEach(() => {
  fetchMock = vi.fn(async () => reponseVide());
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("catalogue", () => {
  it("transmet ses critères au catalogue, pas à la recherche", async () => {
    afficher("/catalogue?domain=droit&language=fr&ordering=-published_at");

    await waitFor(() => {
      const catalogue = adressesDemandees().find((url) => url.includes("/catalog/documents/"));
      expect(catalogue).toContain("domain=droit");
      expect(catalogue).toContain("language=fr");
      expect(catalogue).toContain("ordering=-published_at");
    });
    // Et rien ne part vers la recherche : deux points d'entrée pour une seule
    // liste, c'est ainsi qu'un filtre se perd en route.
    expect(adressesDemandees().some((url) => url.includes("/search/"))).toBe(false);
  });

  it("n'invente pas de critère quand l'adresse n'en porte aucun", async () => {
    afficher("/catalogue");

    await waitFor(() => {
      const catalogue = adressesDemandees().find((url) => url.includes("/catalog/documents/"));
      expect(catalogue).toBeDefined();
      expect(catalogue).not.toContain("domain=");
      expect(catalogue).not.toContain("ordering=");
    });
  });

  it("ne relaie pas une clé que le serveur ne connaît pas", async () => {
    // Le serveur refuse un ordre inconnu : lui transmettre tout ce qui traîne
    // dans l'adresse ferait tomber la page sur un paramètre de suivi collé par
    // un lien partagé.
    afficher("/catalogue?utm_source=whatsapp&domain=droit");

    await waitFor(() => {
      const catalogue = adressesDemandees().find((url) => url.includes("/catalog/documents/"));
      expect(catalogue).toContain("domain=droit");
      expect(catalogue).not.toContain("utm_source");
    });
  });

  it("dit qu'un filtre est trop étroit, pas que le fonds est vide", async () => {
    // Les deux vides ne se corrigent pas de la même façon, et dire au lecteur
    // que le catalogue est vide alors qu'il a filtré serait faux.
    afficher("/catalogue?domain=medecine");

    expect(
      await screen.findByText(/Aucun document ne correspond à ces critères/)
    ).toBeInTheDocument();
  });

  it("annonce un catalogue encore vide quand rien n'a été filtré", async () => {
    afficher("/catalogue");

    expect(
      await screen.findByText(/ne contient pas encore de document public/)
    ).toBeInTheDocument();
  });

  it("garde ses critères en changeant de page", async () => {
    // Sans cela, la page suivante rendait le fonds entier — et le lecteur
    // croyait son filtre encore actif.
    // Une liste non vide : la barre de pagination ne paraît qu'avec des
    // documents à paginer.
    fetchMock.mockImplementation(
      async () =>
        new Response(
          JSON.stringify({
            count: 30,
            next: "http://localhost/api/v1/catalog/documents/?page=2",
            previous: null,
            results: [
              {
                id: 1,
                slug: "un-document",
                title: "Un document",
                abstract: "",
                language_code: "fr",
                publication_year: 2026,
                document_type: null,
                category: "open_resource",
                access_model: "free",
                domain: { id: 1, name: "Droit", slug: "droit" },
                authors: [],
                owner: null,
                page_count: 3,
                cover: null,
                access: { can_read: true, access_model: "free", reason: "free" }
              }
            ]
          }),
          { status: 200 }
        )
    );
    afficher("/catalogue?domain=droit");

    const suivant = await screen.findByRole("link", { name: "Suivant" });
    expect(suivant).toHaveAttribute("href", expect.stringContaining("domain=droit"));
  });
});

describe("panneau de filtres", () => {
  it("montre le critère actif, même arrivé après les options", async () => {
    // Les domaines sont chargés par une seconde requête : `defaultValue` ne se
    // réapplique pas aux options ajoutées ensuite, si bien que le filtre
    // s'appliquait pendant que le panneau affichait « Tous les domaines ».
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).includes("/catalog/domains/")) {
        return new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [{ id: 1, name: "Droit", slug: "droit" }]
          }),
          { status: 200 }
        );
      }
      return reponseVide();
    });

    afficher("/catalogue?domain=droit");

    // Le champ est **réinterrogé** à chaque tentative : l'arrivée des options
    // le remonte, et une référence gardée pointerait sur le nœud remplacé —
    // qui, lui, n'aura jamais la bonne valeur.
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: "Domaine" })).toHaveValue("droit")
    );
  });
});
