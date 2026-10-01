import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StaffDocument } from "@/api/types";
import { tokenStore } from "@/auth/tokenStore";
import { createAppRouter } from "@/router";

afterEach(() => {
  cleanup();
  tokenStore.clear();
  vi.unstubAllGlobals();
});

function staffDocument(overrides: Partial<StaffDocument> = {}): StaffDocument {
  return {
    id: 41,
    slug: "reseaux-informatiques",
    title: "Reseaux informatiques",
    abstract: "Resume",
    language_code: "fr",
    publication_year: 2026,
    category: "voluntary_teacher_deposit",
    access_model: "free",
    publication_status: "draft",
    academic_domain: { id: 3, name: "Informatique" },
    document_type: { id: 1, name: "Cours" },
    owner_organization: null,
    authors: [{ id: 5, display_name: "Levis ANDONGUI", role: "author", position: 1 }],
    rights: null,
    ingestion: null,
    missing_for_submission: ["rights_agreement"],
    missing_for_publication: ["rights_agreement"],
    created_at: "2026-09-27T08:00:00Z",
    updated_at: "2026-09-27T09:00:00Z",
    published_at: null,
    ...overrides
  };
}

interface Routes {
  documents?: (url: URL) => Response;
}

function stubApi({ documents }: Routes = {}) {
  const calls: URL[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    calls.push(url);
    if (url.pathname === "/api/v1/me/") {
      return new Response(
        JSON.stringify({
          id: 7,
          email: "moderation@bibliogabon.ga",
          display_name: "Moderation",
          account_type: "content_admin"
        })
      );
    }
    if (url.pathname === "/api/v1/catalog/domains/") {
      return new Response(
        JSON.stringify({
          count: 1,
          next: null,
          previous: null,
          results: [{ id: 3, name: "Informatique", slug: "informatique" }]
        })
      );
    }
    if (url.pathname === "/api/v1/catalog/types/") {
      return new Response(
        JSON.stringify({
          count: 1,
          next: null,
          previous: null,
          results: [{ id: 1, name: "Cours", slug: "cours" }]
        })
      );
    }
    if (url.pathname === "/api/staff/v1/documents/") {
      return (
        documents?.(url) ??
        new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [staffDocument()]
          })
        )
      );
    }
    return new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls };
}

function renderDocuments() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({
    history: createMemoryHistory({ initialEntries: ["/gestion/documents"] })
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
  return router;
}

function staffCalls(calls: URL[]) {
  return calls.filter((url) => url.pathname === "/api/staff/v1/documents/");
}

beforeEach(() => {
  tokenStore.set({ access: "access-token", refresh: "refresh-token" });
});

describe("liste des documents du back-office", () => {
  it("affiche titre, etat, domaine et type", async () => {
    stubApi();

    renderDocuments();

    const row = await screen.findByRole("row", { name: /Reseaux informatiques/ });
    expect(within(row).getByText("Brouillon")).toBeInTheDocument();
    expect(within(row).getByText("Informatique")).toBeInTheDocument();
    expect(within(row).getByText("Cours")).toBeInTheDocument();
  });

  it("traduit chaque etat de publication du serveur", async () => {
    stubApi({
      documents: () =>
        new Response(
          JSON.stringify({
            count: 3,
            next: null,
            previous: null,
            results: [
              staffDocument({ id: 1, title: "Soumis", publication_status: "submitted" }),
              staffDocument({ id: 2, title: "Publié", publication_status: "published" }),
              staffDocument({ id: 3, title: "Retire", publication_status: "withdrawn" })
            ]
          })
        )
    });

    renderDocuments();

    expect(await screen.findByText("Soumis")).toBeInTheDocument();
    expect(screen.getByText("Publié")).toBeInTheDocument();
    expect(screen.getByText("Retire")).toBeInTheDocument();
  });

  it("montre un code d'etat inconnu plutot que de l'effacer", async () => {
    // Un nouvel etat ajoute au serveur doit se voir, pas disparaitre : une
    // ligne sans badge se lit comme « pas d'etat ».
    stubApi({
      documents: () =>
        new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [staffDocument({ publication_status: "etat_inedit" })]
          })
        )
    });

    renderDocuments();

    expect(await screen.findByText("etat_inedit")).toBeInTheDocument();
  });

  it("pilote la requete avec les filtres d'etat, de domaine, de type et de titre", async () => {
    const { calls } = stubApi();
    renderDocuments();
    await screen.findByRole("row", { name: /Reseaux informatiques/ });

    await userEvent.selectOptions(screen.getByLabelText("État"), "submitted");
    await waitFor(() => {
      expect(staffCalls(calls).at(-1)?.searchParams.get("status")).toBe("submitted");
    });

    await userEvent.selectOptions(screen.getByLabelText("Domaine"), "informatique");
    await waitFor(() => {
      expect(staffCalls(calls).at(-1)?.searchParams.get("domain")).toBe("informatique");
    });

    await userEvent.selectOptions(screen.getByLabelText("Type"), "cours");
    await waitFor(() => {
      expect(staffCalls(calls).at(-1)?.searchParams.get("type")).toBe("cours");
    });

    await userEvent.type(screen.getByLabelText("Titre"), "reseaux");
    await waitFor(() => {
      expect(staffCalls(calls).at(-1)?.searchParams.get("q")).toBe("reseaux");
    });
  });

  it("revient a la premiere page quand un filtre change", async () => {
    // Sans cela, filtrer depuis la page 3 d'un résultat qui n'en compte
    // plus qu'une affiche une liste vide qui ressemble a « aucun document ».
    const { calls } = stubApi({
      documents: () =>
        new Response(
          JSON.stringify({
            count: 60,
            next: "http://127.0.0.1:8000/api/staff/v1/documents/?page=2",
            previous: null,
            results: [staffDocument()]
          })
        )
    });
    renderDocuments();
    await screen.findByRole("row", { name: /Reseaux informatiques/ });

    await userEvent.click(screen.getByRole("button", { name: /suivante/i }));
    await waitFor(() => {
      expect(staffCalls(calls).at(-1)?.searchParams.get("page")).toBe("2");
    });

    await userEvent.selectOptions(screen.getByLabelText("État"), "submitted");

    await waitFor(() => {
      const last = staffCalls(calls).at(-1);
      expect(last?.searchParams.get("status")).toBe("submitted");
      expect(last?.searchParams.get("page")).toBeNull();
    });
  });

  it("pagine avec l'enveloppe de l'API", async () => {
    stubApi({
      documents: () =>
        new Response(
          JSON.stringify({
            count: 42,
            next: "http://127.0.0.1:8000/api/staff/v1/documents/?page=2",
            previous: null,
            results: [staffDocument()]
          })
        )
    });

    renderDocuments();

    expect(await screen.findByText(/42 document/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /suivante/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /precedente/i })).toBeDisabled();
  });

  it("rend un etat de chargement", async () => {
    let release: (() => void) | undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    stubApi({
      documents: () =>
        new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }))
    });
    // On retarde la reponse staff en enveloppant le stub : `documents` est
    // synchrone, la retenue doit donc se faire autour de lui.
    const original = globalThis.fetch;
    vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
      if (new URL(String(input)).pathname === "/api/staff/v1/documents/") {
        await held;
      }
      return original(input, init);
    });

    renderDocuments();

    // Le squelette porte son libelle en aria-label, pas en texte : c'est ce
    // que lit une aide technique, donc c'est ce qu'on interroge. Et on le
    // nomme precisement : le garde de role en affiche un autre pendant
    // l'hydratation de la session, qui disparait ensuite.
    expect(
      await screen.findByRole("status", { name: "Chargement des documents" })
    ).toBeInTheDocument();
    release?.();
  });

  it("rend un etat vide distinct d'un refus", async () => {
    stubApi({
      documents: () =>
        new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }))
    });

    renderDocuments();

    expect(await screen.findByRole("heading", { name: "Aucun document" })).toBeInTheDocument();
  });

  it("rend un refus serveur comme un refus, pas comme une liste vide", async () => {
    stubApi({
      documents: () =>
        new Response(
          JSON.stringify({
            error: {
              code: "permission_denied",
              message: "Vous ne pouvez pas consulter ce perimetre.",
              field_errors: {}
            }
          }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        )
    });

    renderDocuments();

    expect(
      await screen.findByText("Vous ne pouvez pas consulter ce perimetre.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Aucun document" })).not.toBeInTheDocument();
  });

  it("n'affiche jamais de cle de stockage, de chemin de fichier ni d'URL", async () => {
    stubApi({
      documents: () =>
        new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [
              staffDocument({
                ingestion: { version_label: "v1", status: "processed", page_count: 157 }
              })
            ]
          })
        )
    });

    renderDocuments();
    const table = await screen.findByRole("table");

    const rendered = table.textContent ?? "";
    expect(rendered).not.toMatch(/\.pdf/i);
    expect(rendered).not.toMatch(/:\/\//);
    expect(rendered).not.toMatch(/documents\/\d+\/versions/i);
    expect(rendered.toLowerCase()).not.toContain("storage");
    expect(rendered.toLowerCase()).not.toContain("bucket");
  });
});
