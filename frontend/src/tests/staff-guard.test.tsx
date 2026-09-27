import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AccountType } from "@/api/types";
import { tokenStore } from "@/auth/tokenStore";
import { createAppRouter } from "@/router";

afterEach(() => {
  cleanup();
  tokenStore.clear();
  vi.unstubAllGlobals();
});

function signedInAs(accountType: AccountType) {
  tokenStore.set({ access: "access-token", refresh: "refresh-token" });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/v1/me/") {
        return new Response(
          JSON.stringify({
            id: 7,
            email: `${accountType}@bibliogabon.ga`,
            display_name: "Compte de test",
            account_type: accountType
          })
        );
      }
      return new Response(
        JSON.stringify({ count: 0, next: null, previous: null, results: [] })
      );
    })
  );
}

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({
    history: createMemoryHistory({ initialEntries: [path] })
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
  return router;
}

describe("acces a l'espace de gestion", () => {
  it("admet un administrateur de contenu", async () => {
    signedInAs("content_admin");

    renderAt("/gestion");

    expect(await screen.findByRole("heading", { name: /gestion/i })).toBeInTheDocument();
  });

  it("admet un enseignant auteur", async () => {
    signedInAs("teacher_author");

    renderAt("/gestion");

    expect(await screen.findByRole("heading", { name: /gestion/i })).toBeInTheDocument();
  });

  it("refuse un apprenant par un message, sans le rediriger", async () => {
    // Un refus explicite plutot qu'une redirection : renvoyer un lecteur
    // authentifie vers /connexion boucle, puisqu'il est deja connecte.
    signedInAs("individual");

    const router = renderAt("/gestion");

    expect(await screen.findByText(/pas acc(e|è)s/i)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/gestion");
  });

  it("envoie un visiteur anonyme vers la connexion avec le retour", async () => {
    const router = renderAt("/gestion/documents");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/connexion");
    });
    expect(router.state.location.search).toMatchObject({ next: "/gestion/documents" });
  });

  it("n'emboite pas la cible de retour dans elle-meme", async () => {
    // La cible etait lue de facon reactive : apres la redirection, le garde
    // se re-affichait sur /connexion et redirigeait vers
    // /connexion?next=/connexion?next=... L'URL doublait a chaque tour.
    const router = renderAt("/gestion/documents");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/connexion");
    });
    const next = (router.state.location.search as { next?: string }).next ?? "";
    expect(next).toBe("/gestion/documents");
    expect(next).not.toContain("connexion");
    expect(router.state.location.href.length).toBeLessThan(120);
  });
});
