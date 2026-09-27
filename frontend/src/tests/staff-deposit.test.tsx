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

beforeEach(() => {
  tokenStore.set({ access: "access-token", refresh: "refresh-token" });
});

function staffDocument(overrides: Partial<StaffDocument> = {}): StaffDocument {
  return {
    id: 77,
    slug: "algebre-lineaire",
    title: "Algebre lineaire",
    abstract: "",
    language_code: "fr",
    publication_year: null,
    category: "voluntary_teacher_deposit",
    access_model: "free",
    publication_status: "draft",
    academic_domain: null,
    document_type: null,
    owner_organization: null,
    authors: [],
    rights: null,
    ingestion: null,
    missing_for_submission: [],
    missing_for_publication: [],
    created_at: "2026-09-27T08:00:00Z",
    updated_at: "2026-09-27T08:00:00Z",
    published_at: null,
    ...overrides
  };
}

interface Handlers {
  create?: (body: unknown) => Response;
  detail?: () => Response;
  patch?: (body: unknown) => Response;
  submit?: () => Response;
}

function stubApi(handlers: Handlers = {}) {
  const bodies: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      if (body !== undefined) bodies.push(body);

      if (url.pathname === "/api/v1/me/") {
        return new Response(
          JSON.stringify({
            id: 5,
            email: "prof@bibliogabon.ga",
            display_name: "Enseignant",
            account_type: "teacher_author"
          })
        );
      }
      if (url.pathname === "/api/v1/catalog/domains/") {
        return new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [{ id: 3, name: "Mathematiques", slug: "mathematiques" }]
          })
        );
      }
      if (url.pathname === "/api/v1/catalog/types/") {
        return new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [{ id: 1, name: "Cours", slug: "cours", icon: "book", color: "#000" }]
          })
        );
      }
      if (url.pathname === "/api/staff/v1/documents/" && method === "POST") {
        return (
          handlers.create?.(body) ??
          new Response(JSON.stringify(staffDocument()), { status: 201 })
        );
      }
      if (url.pathname === "/api/staff/v1/documents/77/submit/") {
        return handlers.submit?.() ?? new Response(JSON.stringify(staffDocument()));
      }
      if (url.pathname === "/api/staff/v1/documents/77/" && method === "PATCH") {
        return handlers.patch?.(body) ?? new Response(JSON.stringify(staffDocument()));
      }
      if (url.pathname === "/api/staff/v1/documents/77/") {
        return handlers.detail?.() ?? new Response(JSON.stringify(staffDocument()));
      }
      return new Response(
        JSON.stringify({ count: 0, next: null, previous: null, results: [] })
      );
    })
  );
  return { bodies };
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

function refusal(fieldErrors: Record<string, string[]>, message = "Le document est invalide.") {
  return new Response(
    JSON.stringify({ error: { code: "invalid_request", message, field_errors: fieldErrors } }),
    { status: 400, headers: { "Content-Type": "application/json" } }
  );
}

describe("creation d'un brouillon", () => {
  it("cree avec le minimum et va sur la fiche du document", async () => {
    const { bodies } = stubApi();
    const router = renderAt("/gestion/documents/nouveau");

    await userEvent.type(await screen.findByLabelText(/^Titre/), "Algebre lineaire");
    await userEvent.type(screen.getByLabelText(/^Identifiant/), "algebre-lineaire");
    await userEvent.selectOptions(
      screen.getByLabelText(/^Categorie/),
      "voluntary_teacher_deposit"
    );
    await userEvent.selectOptions(screen.getByLabelText(/^Modele d'acces/), "free");
    await userEvent.click(screen.getByRole("button", { name: /creer le brouillon/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/gestion/documents/77");
    });
    expect(bodies[0]).toMatchObject({
      title: "Algebre lineaire",
      slug: "algebre-lineaire",
      category: "voluntary_teacher_deposit",
      access_model: "free"
    });
  });

  it("place un refus serveur sur le bon champ", async () => {
    stubApi({ create: () => refusal({ slug: ["Cet identifiant est deja utilise."] }) });
    renderAt("/gestion/documents/nouveau");

    await userEvent.type(await screen.findByLabelText(/^Titre/), "Doublon");
    await userEvent.type(screen.getByLabelText(/^Identifiant/), "algebre-lineaire");
    await userEvent.selectOptions(screen.getByLabelText(/^Categorie/), "open_resource");
    await userEvent.selectOptions(screen.getByLabelText(/^Modele d'acces/), "free");
    await userEvent.click(screen.getByRole("button", { name: /creer le brouillon/i }));

    const input = await screen.findByLabelText(/^Identifiant/);
    expect(input).toHaveAttribute("aria-invalid", "true");
    const describedBy = input.getAttribute("aria-describedby");
    expect(document.getElementById(describedBy as string)).toHaveTextContent(
      "Cet identifiant est deja utilise."
    );
  });
});

describe("fiche d'un document", () => {
  it("enregistre les metadonnees et reflete la reponse du serveur", async () => {
    const { bodies } = stubApi({
      patch: () =>
        new Response(
          JSON.stringify(
            staffDocument({
              title: "Algebre lineaire avancee",
              academic_domain: { id: 3, name: "Mathematiques" },
              document_type: { id: 1, name: "Cours" }
            })
          )
        )
    });
    renderAt("/gestion/documents/77");

    const title = await screen.findByLabelText(/^Titre/);
    await userEvent.clear(title);
    await userEvent.type(title, "Algebre lineaire avancee");
    await screen.findByRole("option", { name: "Mathematiques" });
    await userEvent.selectOptions(screen.getByLabelText(/^Domaine/), "3");
    await userEvent.selectOptions(screen.getByLabelText(/^Type/), "1");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer les metadonnees/i }));

    await waitFor(() => {
      expect(bodies.at(-1)).toMatchObject({
        title: "Algebre lineaire avancee",
        academic_domain: 3,
        document_type: 1
      });
    });
    expect(await screen.findByDisplayValue("Algebre lineaire avancee")).toBeInTheDocument();
  });

  it("envoie des identifiants numeriques, pas des slugs, pour le domaine et le type", async () => {
    // Les filtres de la liste prennent des slugs, l'ecriture prend des ids.
    // Confondre les deux produit un 400 que rien n'explique a l'ecran.
    const { bodies } = stubApi();
    renderAt("/gestion/documents/77");

    // La liste des domaines arrive de facon asynchrone : selectionner avant
    // qu'elle soit peuplee echoue sur une option absente.
    await screen.findByRole("option", { name: "Mathematiques" });
    await userEvent.selectOptions(screen.getByLabelText(/^Domaine/), "3");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer les metadonnees/i }));

    await waitFor(() => {
      expect(bodies.at(-1)).toMatchObject({ academic_domain: 3 });
    });
    expect(JSON.stringify(bodies.at(-1))).not.toContain("mathematiques");
  });
});

describe("liste de completude", () => {
  it("traduit chaque code manquant en francais", async () => {
    stubApi({
      detail: () =>
        new Response(
          JSON.stringify(
            staffDocument({
              missing_for_submission: ["academic_domain", "author", "rights_agreement"]
            })
          )
        )
    });
    renderAt("/gestion/documents/77");

    const checklist = await screen.findByRole("list", { name: /fournir/i });
    expect(within(checklist).getByText(/domaine/i)).toBeInTheDocument();
    expect(within(checklist).getByText(/auteur/i)).toBeInTheDocument();
    expect(within(checklist).getByText(/droits/i)).toBeInTheDocument();
  });

  it("montre un code inconnu tel quel plutot que de l'omettre", async () => {
    // Un nouveau code cote serveur doit apparaitre, meme non traduit : une
    // liste qui l'omet dirait au deposant qu'il ne manque rien, alors que la
    // soumission sera refusee.
    stubApi({
      detail: () =>
        new Response(
          JSON.stringify(staffDocument({ missing_for_submission: ["exigence_inedite"] }))
        )
    });
    renderAt("/gestion/documents/77");

    const checklist = await screen.findByRole("list", { name: /fournir/i });
    expect(within(checklist).getByText("exigence_inedite")).toBeInTheDocument();
  });

  it("interdit la soumission tant qu'il manque quelque chose", async () => {
    stubApi({
      detail: () =>
        new Response(
          JSON.stringify(staffDocument({ missing_for_submission: ["rights_agreement"] }))
        )
    });
    renderAt("/gestion/documents/77");

    expect(await screen.findByRole("button", { name: /soumettre/i })).toBeDisabled();
  });

  it("disparait et libere la soumission quand plus rien ne manque", async () => {
    stubApi({ detail: () => new Response(JSON.stringify(staffDocument())) });
    renderAt("/gestion/documents/77");

    expect(await screen.findByRole("button", { name: /soumettre/i })).toBeEnabled();
    expect(screen.queryByRole("list", { name: /fournir/i })).not.toBeInTheDocument();
  });

  it("n'affiche aucun chemin de fichier ni URL sur la fiche", async () => {
    stubApi({
      detail: () =>
        new Response(
          JSON.stringify(
            staffDocument({
              ingestion: { version_label: "v1", status: "processed", page_count: 42 }
            })
          )
        )
    });
    renderAt("/gestion/documents/77");
    await screen.findByLabelText(/^Titre/);

    const rendered = document.body.textContent ?? "";
    expect(rendered).not.toMatch(/\.pdf/i);
    expect(rendered).not.toMatch(/:\/\//);
    expect(rendered.toLowerCase()).not.toContain("storage");
  });
});
