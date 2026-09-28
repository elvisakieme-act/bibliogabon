import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StaffMembership } from "@/api/types";
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

function membership(overrides: Partial<StaffMembership> = {}): StaffMembership {
  return {
    id: 11,
    user: { id: 21, email: "membre@uob.ga", display_name: "Sarah MOUSSAVOU" },
    role: "member",
    status: "active",
    verification_status: "verified",
    verification_method: "student_card",
    starts_at: "2026-09-01T08:00:00Z",
    ends_at: null,
    ...overrides
  };
}

interface Handlers {
  list?: () => Response;
  members?: () => Response;
  quotas?: () => Response;
  report?: () => Response;
  suspend?: (body: unknown) => Response;
  add?: (body: unknown) => Response;
}

function stubApi(handlers: Handlers = {}) {
  const calls: URL[] = [];
  const bodies: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      calls.push(url);
      if (init?.body) bodies.push(JSON.parse(String(init.body)));

      if (url.pathname === "/api/v1/me/") {
        return new Response(
          JSON.stringify({
            id: 7,
            email: "recteur@uob.ga",
            display_name: "Recteur UOB",
            account_type: "organization_admin"
          })
        );
      }
      if (url.pathname === "/api/staff/v1/organizations/" && method === "GET") {
        return (
          handlers.list?.() ??
          new Response(
            JSON.stringify({
              count: 1,
              next: null,
              previous: null,
              results: [
                {
                  id: 3,
                  name: "UOB",
                  slug: "uob",
                  organization_type: "university",
                  status: "active",
                  requires_identity_verification: true
                }
              ]
            })
          )
        );
      }
      if (url.pathname === "/api/staff/v1/organizations/3/members/" && method === "POST") {
        return (
          handlers.add?.(bodies.at(-1)) ??
          new Response(JSON.stringify(membership()), { status: 201 })
        );
      }
      if (url.pathname === "/api/staff/v1/organizations/3/members/") {
        return (
          handlers.members?.() ??
          new Response(
            JSON.stringify({ count: 1, next: null, previous: null, results: [membership()] })
          )
        );
      }
      if (url.pathname === "/api/staff/v1/organizations/3/members/11/suspend/") {
        return (
          handlers.suspend?.(bodies.at(-1)) ??
          new Response(JSON.stringify(membership({ status: "suspended" })))
        );
      }
      if (url.pathname === "/api/staff/v1/organizations/3/quotas/") {
        return (
          handlers.quotas?.() ??
          new Response(
            JSON.stringify({
              count: 1,
              next: null,
              previous: null,
              results: [
                {
                  id: 5,
                  status: "active",
                  seat_limit: 250,
                  offer: { id: 2, name: "Offre institutionnelle" },
                  contract_reference: "CONTRAT-UOB-2026",
                  starts_at: "2026-01-01T00:00:00Z",
                  ends_at: "2026-12-31T00:00:00Z"
                }
              ]
            })
          )
        );
      }
      if (url.pathname === "/api/staff/v1/organizations/3/report/") {
        return (
          handlers.report?.() ??
          new Response(
            JSON.stringify({
              id: 9,
              organization: { id: 3, name: "UOB", slug: "uob" },
              period: { start: "2026-09-01", end: "2026-09-30" },
              status: "generated",
              metrics: {
                access: { active_member_count: 42 },
                usage: { reader_session_count: 310, page_view_count: 2480 },
                commercial: { payments: { succeeded_count: 1 } },
                support: { opened_count: 2, resolved_count: 1 }
              },
              generated_at: "2026-09-28T08:00:00Z"
            })
          )
        );
      }
      if (url.pathname === "/api/staff/v1/organizations/3/") {
        return new Response(
          JSON.stringify({
            id: 3,
            name: "UOB",
            slug: "uob",
            organization_type: "university",
            status: "active",
            requires_identity_verification: true,
            active_member_count: 42
          })
        );
      }
      return new Response(
        JSON.stringify({ count: 0, next: null, previous: null, results: [] })
      );
    })
  );
  return { calls, bodies };
}

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({ history: createMemoryHistory({ initialEntries: [path] }) });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
  return router;
}

describe("liste des organisations", () => {
  it("affiche celles que l'on administre", async () => {
    stubApi();

    renderAt("/gestion/organisations");

    expect(await screen.findByRole("link", { name: "UOB" })).toBeInTheDocument();
  });

  it("rend le refus du serveur plutôt qu'une liste vide", async () => {
    stubApi({
      list: () =>
        new Response(
          JSON.stringify({
            error: {
              code: "permission_denied",
              message: "Vous n'administrez aucune organisation.",
              field_errors: {}
            }
          }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        )
    });

    renderAt("/gestion/organisations");

    expect(
      await screen.findByText("Vous n'administrez aucune organisation.")
    ).toBeInTheDocument();
  });
});

describe("fiche d'une organisation", () => {
  it("montre les membres, les quotas et le rapport", async () => {
    stubApi();

    renderAt("/gestion/organisations/3");

    expect(await screen.findByText("Sarah MOUSSAVOU")).toBeInTheDocument();
    expect(screen.getByText("CONTRAT-UOB-2026")).toBeInTheDocument();
    expect(await screen.findByText(/310/)).toBeInTheDocument();
  });

  it("marque visiblement une adhésion non vérifiée", async () => {
    // Une adhésion non vérifiée n'accorde rien. Un administrateur qui ne le
    // voit pas conclura que la plateforme est cassée.
    stubApi({
      members: () =>
        new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [membership({ verification_status: "unverified" })]
          })
        )
    });

    renderAt("/gestion/organisations/3");

    const row = await screen.findByRole("row", { name: /Sarah MOUSSAVOU/ });
    expect(within(row).getByText(/non vérifiée/i)).toBeInTheDocument();
    expect(within(row).getByText(/n'accorde aucun accès/i)).toBeInTheDocument();
  });

  it("suspend un membre avec un motif", async () => {
    const { bodies } = stubApi();
    renderAt("/gestion/organisations/3");

    await userEvent.click(
      await screen.findByRole("button", { name: /suspendre Sarah MOUSSAVOU/i })
    );
    await userEvent.type(screen.getByLabelText(/Motif/i), "Congé sabbatique.");
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    await waitFor(() => {
      expect(bodies.at(-1)).toMatchObject({ reason: "Congé sabbatique." });
    });
  });

  it("refuse une suspension sans motif avant d'appeler le serveur", async () => {
    // Le serveur accepterait un motif vide sur cette route — il ne l'exige pas
    // — et l'audit perdrait alors la raison de la suspension. La vérification
    // côté client n'est donc pas une commodité ici, c'est la garantie.
    const { calls } = stubApi();
    renderAt("/gestion/organisations/3");

    await userEvent.click(
      await screen.findByRole("button", { name: /suspendre Sarah MOUSSAVOU/i })
    );
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/motif est obligatoire/i);
    expect(calls.filter((url) => url.pathname.endsWith("/suspend/"))).toHaveLength(0);
  });

  it("rend le refus serveur d'une suspension", async () => {
    stubApi({
      suspend: () =>
        new Response(
          JSON.stringify({
            error: {
              code: "permission_denied",
              message: "Gestion des membres refusée.",
              field_errors: {}
            }
          }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        )
    });
    renderAt("/gestion/organisations/3");

    await userEvent.click(
      await screen.findByRole("button", { name: /suspendre Sarah MOUSSAVOU/i })
    );
    await userEvent.type(screen.getByLabelText(/Motif/i), "Motif.");
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Gestion des membres refusée/);
  });

  it("rattache un membre par son adresse et rend le refus d'un compte inconnu", async () => {
    stubApi({
      add: () =>
        new Response(
          JSON.stringify({
            error: {
              code: "invalid_request",
              message: "Aucun compte ne correspond à cette adresse.",
              field_errors: { email: ["Cette personne doit d'abord créer un compte."] }
            }
          }),
          { status: 400, headers: { "Content-Type": "application/json" } }
        )
    });
    renderAt("/gestion/organisations/3");

    await userEvent.type(
      await screen.findByLabelText(/Adresse du compte/i),
      "inconnu@example.ga"
    );
    await userEvent.click(screen.getByRole("button", { name: /rattacher/i }));

    const field = await screen.findByLabelText(/Adresse du compte/i);
    await waitFor(() => expect(field).toHaveAttribute("aria-invalid", "true"));
    expect(
      document.getElementById(field.getAttribute("aria-describedby") as string)
    ).toHaveTextContent(/créer un compte/);
  });

  it("n'attache aucun chiffre de lecture à une personne", async () => {
    // Exclusion, pas report : un écran qui dirait qui a lu quoi transformerait
    // une bibliothèque en outil de surveillance.
    //
    // La vérification est structurelle et non textuelle. Chercher la phrase
    // « a lu » attrapait la phrase par laquelle l'écran *explique* qu'il ne
    // le dit pas — un test qui punit le code d'être explicite finit par
    // pousser à retirer l'explication.
    stubApi();
    renderAt("/gestion/organisations/3");
    const table = await screen.findByRole("table");

    const headers = Array.from(table.querySelectorAll("th[scope=col]")).map(
      (cell) => cell.textContent ?? ""
    );
    expect(headers.join(" ")).not.toMatch(/lecture|pages|sessions|consult/i);

    const row = screen.getByRole("row", { name: /Sarah MOUSSAVOU/ });
    expect(row.textContent ?? "").not.toMatch(/\d+\s*(pages?|sessions?|lectures?)/i);

    expect(document.body.textContent ?? "").not.toMatch(/:\/\//);
  });
});
