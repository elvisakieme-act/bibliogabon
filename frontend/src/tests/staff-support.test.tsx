import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StaffTicket } from "@/api/types";
import { tokenStore } from "@/auth/tokenStore";
import { createAppRouter } from "@/router";

afterEach(() => {
  cleanup();
  tokenStore.clear();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  tokenStore.set({ access: "access-token", refresh: "refresh-token" });
});

function ticket(overrides: Partial<StaffTicket> = {}): StaffTicket {
  return {
    id: 31,
    category: "support",
    status: "open",
    priority: "normal",
    title: "Paiement refusé",
    description: "Ma carte est rejetée à chaque tentative.",
    created_by: { id: 21, display_name: "Sarah MOUSSAVOU" },
    assigned_to: null,
    document: null,
    organization: null,
    resolution_summary: "",
    opened_at: "2026-09-27T09:00:00Z",
    resolved_at: null,
    ...overrides
  };
}

interface Handlers {
  list?: (url: URL) => Response;
  resolve?: (body: unknown) => Response;
}

function stubApi(handlers: Handlers = {}) {
  const calls: URL[] = [];
  const bodies: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      calls.push(url);
      if (init?.body) bodies.push(JSON.parse(String(init.body)));

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
      if (url.pathname === "/api/staff/v1/tickets/31/resolve/") {
        return (
          handlers.resolve?.(bodies.at(-1)) ??
          new Response(
            JSON.stringify(ticket({ status: "resolved", resolution_summary: "Traité." }))
          )
        );
      }
      if (url.pathname === "/api/staff/v1/tickets/") {
        return (
          handlers.list?.(url) ??
          new Response(
            JSON.stringify({ count: 1, next: null, previous: null, results: [ticket()] })
          )
        );
      }
      return new Response(
        JSON.stringify({ count: 0, next: null, previous: null, results: [] })
      );
    })
  );
  return { calls, bodies };
}

function renderSupport() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({
    history: createMemoryHistory({ initialEntries: ["/gestion/support"] })
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
  return router;
}

function ticketCalls(calls: URL[]) {
  return calls.filter((url) => url.pathname === "/api/staff/v1/tickets/");
}

describe("file de support", () => {
  it("affiche les demandes en attente", async () => {
    stubApi();

    renderSupport();

    expect(await screen.findByText("Paiement refusé")).toBeInTheDocument();
    expect(screen.getByText(/Sarah MOUSSAVOU/)).toBeInTheDocument();
  });

  it("filtre par catégorie et par état", async () => {
    const { calls } = stubApi();
    renderSupport();
    await screen.findByText("Paiement refusé");

    await userEvent.selectOptions(screen.getByLabelText(/Catégorie/i), "withdrawal_request");
    await waitFor(() => {
      expect(ticketCalls(calls).at(-1)?.searchParams.get("category")).toBe(
        "withdrawal_request"
      );
    });

    await userEvent.selectOptions(screen.getByLabelText(/^État/i), "resolved");
    await waitFor(() => {
      expect(ticketCalls(calls).at(-1)?.searchParams.get("status")).toBe("resolved");
    });
  });

  it("traduit chaque catégorie", async () => {
    stubApi({
      list: () =>
        new Response(
          JSON.stringify({
            count: 3,
            next: null,
            previous: null,
            results: [
              ticket({ id: 1, category: "support", title: "Question" }),
              ticket({ id: 2, category: "document_report", title: "Signalement" }),
              ticket({ id: 3, category: "withdrawal_request", title: "Retrait" })
            ]
          })
        )
    });

    renderSupport();

    expect(await screen.findByText("Demande de support")).toBeInTheDocument();
    expect(screen.getByText("Signalement de document")).toBeInTheDocument();
    expect(screen.getByText("Demande de retrait")).toBeInTheDocument();
  });

  it("montre une catégorie inconnue telle quelle", async () => {
    stubApi({
      list: () =>
        new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [ticket({ category: "categorie_inedite" as StaffTicket["category"] })]
          })
        )
    });

    renderSupport();

    expect(await screen.findByText("categorie_inedite")).toBeInTheDocument();
  });

  it("dit clairement qu'une demande de retrait ne retire rien, et lie le document", async () => {
    // Un modérateur qui croit qu'en fermant le ticket il a retiré le document
    // laissera en ligne un contenu dont le retrait a été accordé.
    stubApi({
      list: () =>
        new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [
              ticket({
                category: "withdrawal_request",
                title: "Demande de retrait : Algebre",
                document: { id: 77, title: "Algebre lineaire", slug: "algebre-lineaire" }
              })
            ]
          })
        )
    });

    renderSupport();

    const row = await screen.findByRole("listitem", { name: /Demande de retrait/ });
    expect(within(row).getByRole("link", { name: /Algebre lineaire/ })).toHaveAttribute(
      "href",
      "/gestion/documents/77"
    );
    expect(within(row).getByText(/ne retire pas le document/i)).toBeInTheDocument();
  });

  it("refuse une résolution sans résumé avant d'appeler le serveur", async () => {
    const { calls } = stubApi();
    renderSupport();

    await userEvent.click(await screen.findByRole("button", { name: /résoudre/i }));
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/résumé/i);
    expect(calls.filter((url) => url.pathname.endsWith("/resolve/"))).toHaveLength(0);
  });

  it("résout avec le résumé saisi", async () => {
    const { bodies } = stubApi();
    renderSupport();

    await userEvent.click(await screen.findByRole("button", { name: /résoudre/i }));
    await userEvent.type(
      screen.getByLabelText(/Résumé de la résolution/i),
      "Remboursement effectué."
    );
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    await waitFor(() => {
      expect(bodies.at(-1)).toMatchObject({ resolution_summary: "Remboursement effectué." });
    });
  });

  it("rend le refus serveur d'une résolution", async () => {
    stubApi({
      resolve: () =>
        new Response(
          JSON.stringify({
            error: {
              code: "resolution_refused",
              message: "support ticket is already closed",
              field_errors: {}
            }
          }),
          { status: 409, headers: { "Content-Type": "application/json" } }
        )
    });
    renderSupport();

    await userEvent.click(await screen.findByRole("button", { name: /résoudre/i }));
    await userEvent.type(screen.getByLabelText(/Résumé de la résolution/i), "Traité.");
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/already closed/);
  });

  it("rend un état vide distinct d'un refus", async () => {
    stubApi({
      list: () =>
        new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }))
    });

    renderSupport();

    expect(await screen.findByRole("heading", { name: /Aucune demande/i })).toBeInTheDocument();
  });

  it("rend le refus du serveur plutôt qu'une file vide", async () => {
    stubApi({
      list: () =>
        new Response(
          JSON.stringify({
            error: {
              code: "permission_denied",
              message: "Vous n'avez pas accès à la file de support.",
              field_errors: {}
            }
          }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        )
    });

    renderSupport();

    expect(
      await screen.findByText("Vous n'avez pas accès à la file de support.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Aucune demande/i })).not.toBeInTheDocument();
  });

  it("n'affiche ni chemin de fichier ni URL", async () => {
    stubApi();
    renderSupport();
    await screen.findByText("Paiement refusé");

    const rendered = document.body.textContent ?? "";
    expect(rendered).not.toMatch(/\.pdf/i);
    expect(rendered).not.toMatch(/:\/\//);
    expect(rendered.toLowerCase()).not.toContain("storage");
  });
});
