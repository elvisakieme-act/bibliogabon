import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StaffDocument, StaffReview } from "@/api/types";
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

function staffDocument(overrides: Partial<StaffDocument> = {}): StaffDocument {
  return {
    id: 51,
    slug: "these-de-droit",
    title: "These de droit",
    abstract: "",
    language_code: "fr",
    publication_year: 2026,
    category: "voluntary_teacher_deposit",
    access_model: "free",
    publication_status: "submitted",
    academic_domain: { id: 3, name: "Droit" },
    document_type: { id: 1, name: "Memoire" },
    owner_organization: null,
    authors: [{ id: 9, display_name: "Aline NZE", role: "author", position: 1 }],
    rights: {
      agreement_type: "teacher_voluntary",
      rights_holder_name: "Aline NZE",
      authorization_status: "approved",
      withdrawal_rule: "author_request",
      valid_for_publication: true
    },
    ingestion: { version_label: "v1", status: "processed", page_count: 87 },
    missing_for_submission: [],
    missing_for_publication: [],
    created_at: "2026-09-27T08:00:00Z",
    updated_at: "2026-09-27T09:00:00Z",
    published_at: null,
    ...overrides
  };
}

function review(overrides: Partial<StaffReview> = {}): StaffReview {
  return {
    id: 4,
    status: "open",
    document: staffDocument(),
    opened_by: { id: 7, display_name: "Moderation" },
    reviewer: null,
    decided_by: null,
    decision_reason: "",
    internal_notes: "",
    opened_at: "2026-09-27T09:30:00Z",
    decided_at: null,
    ...overrides
  };
}

interface Handlers {
  list?: (url: URL) => Response;
  detail?: () => Response;
  decision?: (body: unknown) => Response;
  assign?: () => Response;
  account?: string;
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
            email: "moderation@bibliogabon.ga",
            display_name: "Moderation",
            account_type: handlers.account ?? "content_admin"
          })
        );
      }
      if (url.pathname === "/api/staff/v1/reviews/" && method === "GET") {
        return (
          handlers.list?.(url) ??
          new Response(
            JSON.stringify({ count: 1, next: null, previous: null, results: [review()] })
          )
        );
      }
      if (url.pathname === "/api/staff/v1/reviews/4/decision/") {
        return handlers.decision?.(bodies.at(-1)) ?? new Response(JSON.stringify(review()));
      }
      if (url.pathname === "/api/staff/v1/reviews/4/assign/") {
        return (
          handlers.assign?.() ??
          new Response(
            JSON.stringify(review({ reviewer: { id: 7, display_name: "Moderation" } }))
          )
        );
      }
      if (url.pathname === "/api/staff/v1/reviews/4/") {
        return handlers.detail?.() ?? new Response(JSON.stringify(review()));
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

function reviewCalls(calls: URL[]) {
  return calls.filter((url) => url.pathname === "/api/staff/v1/reviews/");
}

describe("file de revue", () => {
  it("affiche chaque dossier en attente avec son document", async () => {
    stubApi();

    renderAt("/gestion/revues");

    const row = await screen.findByRole("row", { name: /These de droit/ });
    expect(within(row).getByText("Aline NZE")).toBeInTheDocument();
  });

  it("dit ce qui bloque encore la publication, avant d'ouvrir le dossier", async () => {
    // Un relecteur doit voir depuis la file qu'un dossier n'est pas prêt :
    // ouvrir pour découvrir un bouton grisé est une perte de temps.
    stubApi({
      list: () =>
        new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [
              review({
                document: staffDocument({
                  missing_for_publication: ["rights_agreement_not_approved"]
                })
              })
            ]
          })
        )
    });

    renderAt("/gestion/revues");

    expect(await screen.findByText(/approbation de la déclaration/i)).toBeInTheDocument();
  });

  it("filtre par état et par attribution", async () => {
    const { calls } = stubApi();
    renderAt("/gestion/revues");
    await screen.findByRole("row", { name: /These de droit/ });

    await userEvent.selectOptions(screen.getByLabelText(/Attribution/i), "me");
    await waitFor(() => {
      expect(reviewCalls(calls).at(-1)?.searchParams.get("assigned")).toBe("me");
    });

    await userEvent.selectOptions(screen.getByLabelText(/^État/i), "approved");
    await waitFor(() => {
      expect(reviewCalls(calls).at(-1)?.searchParams.get("status")).toBe("approved");
    });
  });

  it("rend un état vide distinct d'un refus", async () => {
    stubApi({
      list: () =>
        new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }))
    });

    renderAt("/gestion/revues");

    expect(
      await screen.findByRole("heading", { name: /Aucun dossier en attente/i })
    ).toBeInTheDocument();
  });

  it("rend le refus du serveur plutôt qu'une file vide", async () => {
    // Cacher un lien est une courtoisie ; l'écran doit rendre un refus.
    stubApi({
      account: "teacher_author",
      list: () =>
        new Response(
          JSON.stringify({
            error: {
              code: "permission_denied",
              message: "Seul un modérateur de contenu accède à la file.",
              field_errors: {}
            }
          }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        )
    });

    renderAt("/gestion/revues");

    expect(
      await screen.findByText("Seul un modérateur de contenu accède à la file.")
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /Aucun dossier en attente/i })
    ).not.toBeInTheDocument();
  });

  it("n'affiche ni clé de stockage ni URL", async () => {
    stubApi();

    renderAt("/gestion/revues");
    const table = await screen.findByRole("table");

    const rendered = table.textContent ?? "";
    expect(rendered).not.toMatch(/\.pdf/i);
    expect(rendered).not.toMatch(/:\/\//);
    expect(rendered.toLowerCase()).not.toContain("storage");
  });
});

describe("écran de décision", () => {
  it("montre les droits, le traitement et le nombre de pages", async () => {
    stubApi();

    renderAt("/gestion/revues/4");

    expect(await screen.findByRole("heading", { name: /These de droit/ })).toBeInTheDocument();
    expect(screen.getByText(/Approuvée/)).toBeInTheDocument();
    expect(screen.getByText(/87/)).toBeInTheDocument();
  });

  it("dit ce qui bloque l'approbation, au lieu de seulement griser le bouton", async () => {
    // Une porte fermée sans raison visible se lit comme une panne, et le
    // relecteur conclut que l'outil est cassé.
    stubApi({
      detail: () =>
        new Response(
          JSON.stringify(
            review({
              document: staffDocument({
                missing_for_publication: ["rights_agreement_not_approved"]
              })
            })
          )
        )
    });

    renderAt("/gestion/revues/4");

    expect(await screen.findByRole("button", { name: /approuver/i })).toBeDisabled();
    expect(screen.getByText(/approbation de la déclaration/i)).toBeInTheDocument();
  });

  it("refuse un rejet sans motif avant même d'appeler le serveur", async () => {
    const { calls } = stubApi();
    renderAt("/gestion/revues/4");

    await userEvent.click(await screen.findByRole("button", { name: /rejeter/i }));

    expect(await screen.findByText(/motif/i)).toBeInTheDocument();
    expect(calls.filter((url) => url.pathname.endsWith("/decision/"))).toHaveLength(0);
  });

  it("approuve avec le motif saisi", async () => {
    const { bodies } = stubApi();
    renderAt("/gestion/revues/4");

    await userEvent.type(
      await screen.findByLabelText(/Motif de la décision/i),
      "Droits vérifiés, contenu conforme."
    );
    await userEvent.click(screen.getByRole("button", { name: /approuver/i }));

    await waitFor(() => {
      expect(bodies.at(-1)).toMatchObject({
        decision: "approved",
        reason: "Droits vérifiés, contenu conforme."
      });
    });
  });

  it("place un refus serveur sur le bon champ", async () => {
    stubApi({
      decision: () =>
        new Response(
          JSON.stringify({
            error: {
              code: "invalid_request",
              message: "Décision invalide.",
              field_errors: { reason: ["Un rejet doit être motivé, pour l'audit interne."] }
            }
          }),
          { status: 400, headers: { "Content-Type": "application/json" } }
        )
    });
    renderAt("/gestion/revues/4");

    await userEvent.type(await screen.findByLabelText(/Motif de la décision/i), "x");
    await userEvent.click(screen.getByRole("button", { name: /rejeter/i }));

    const field = await screen.findByLabelText(/Motif de la décision/i);
    await waitFor(() => expect(field).toHaveAttribute("aria-invalid", "true"));
    const describedBy = field.getAttribute("aria-describedby");
    expect(document.getElementById(describedBy as string)).toHaveTextContent(/motivé/);
  });

  it("rend lisiblement le refus d'auto-relecture", async () => {
    stubApi({
      decision: () =>
        new Response(
          JSON.stringify({
            error: {
              code: "self_review_forbidden",
              message: "Vous ne pouvez pas décider sur un document dont vous êtes auteur.",
              field_errors: {}
            }
          }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        )
    });
    renderAt("/gestion/revues/4");

    await userEvent.type(await screen.findByLabelText(/Motif de la décision/i), "Conforme.");
    await userEvent.click(screen.getByRole("button", { name: /approuver/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/dont vous êtes auteur/);
  });

  it("permet de se saisir du dossier", async () => {
    const { calls } = stubApi();
    renderAt("/gestion/revues/4");

    await userEvent.click(await screen.findByRole("button", { name: /me saisir/i }));

    await waitFor(() => {
      expect(calls.some((url) => url.pathname.endsWith("/assign/"))).toBe(true);
    });
  });

  it("n'offre aucune commande d'approbation des droits", async () => {
    // D014 a fait de `RightsAgreement.authorization_status` la seule
    // représentation de cette barrière. Une seconde commande ici serait une
    // seconde réponse à une même question.
    stubApi();

    renderAt("/gestion/revues/4");
    await screen.findByRole("heading", { name: /These de droit/ });

    expect(
      screen.queryByRole("button", { name: /approuver les droits/i })
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/référence d'audit/i)).not.toBeInTheDocument();
  });
});
