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
  account?: string;
  index?: () => Response;
  audit?: () => Response;
  withdraw?: (body: unknown) => Response;
  archive?: (body: unknown) => Response;
  create?: (body: unknown) => Response;
  detail?: () => Response;
  patch?: (body: unknown) => Response;
  submit?: () => Response;
  attachAuthor?: (body: unknown) => Response;
  detachAuthor?: () => Response;
  rights?: (body: unknown) => Response;
}

function stubApi(handlers: Handlers = {}) {
  const calls: URL[] = [];
  const bodies: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      calls.push(url);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      if (body !== undefined) bodies.push(body);

      if (url.pathname === "/api/v1/me/") {
        return new Response(
          JSON.stringify({
            id: 5,
            email: "prof@bibliogabon.ga",
            display_name: "Enseignant",
            account_type: handlers.account ?? "teacher_author"
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
      if (url.pathname === "/api/staff/v1/") {
        return (
          handlers.index?.() ??
          new Response(
            JSON.stringify({
              name: "BiblioGABON staff API",
              version: "v1",
              schema: "/api/staff/v1/schema/",
              upload: { max_bytes: 209715200, accepted_mime_types: ["application/pdf"] }
            })
          )
        );
      }
      if (url.pathname === "/api/staff/v1/documents/77/audit/") {
        return (
          handlers.audit?.() ??
          new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }))
        );
      }
      if (url.pathname === "/api/staff/v1/documents/77/withdraw/") {
        return (
          handlers.withdraw?.(body) ??
          new Response(JSON.stringify(staffDocument({ publication_status: "withdrawn" })))
        );
      }
      if (url.pathname === "/api/staff/v1/documents/77/archive/") {
        return (
          handlers.archive?.(body) ??
          new Response(JSON.stringify(staffDocument({ publication_status: "archived" })))
        );
      }
      if (url.pathname === "/api/staff/v1/authors/") {
        return new Response(
          JSON.stringify({
            count: 2,
            next: null,
            previous: null,
            results: [
              { id: 9, display_name: "Aline NZE", author_type: "person", affiliation: "UOB" },
              { id: 10, display_name: "Brice ONDO", author_type: "person", affiliation: "USTM" }
            ]
          })
        );
      }
      if (url.pathname === "/api/staff/v1/documents/77/authors/" && method === "POST") {
        return (
          handlers.attachAuthor?.(body) ??
          new Response(
            JSON.stringify(
              staffDocument({
                authors: [{ id: 9, display_name: "Aline NZE", role: "coauthor", position: 1 }]
              })
            ),
            { status: 201 }
          )
        );
      }
      if (
        url.pathname.startsWith("/api/staff/v1/documents/77/authors/") &&
        method === "DELETE"
      ) {
        return handlers.detachAuthor?.() ?? new Response(null, { status: 204 });
      }
      if (url.pathname === "/api/staff/v1/documents/77/rights/" && method === "PUT") {
        return (
          handlers.rights?.(body) ??
          new Response(
            JSON.stringify(
              staffDocument({
                rights: {
                  agreement_type: "teacher_voluntary",
                  rights_holder_name: "Aline NZE",
                  authorization_status: "pending_review",
                  withdrawal_rule: "author_request",
                  valid_for_publication: false
                }
              })
            )
          )
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
      screen.getByLabelText(/^Catégorie/),
      "voluntary_teacher_deposit"
    );
    await userEvent.selectOptions(screen.getByLabelText(/^Modèle d'accès/), "free");
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
    await userEvent.selectOptions(screen.getByLabelText(/^Catégorie/), "open_resource");
    await userEvent.selectOptions(screen.getByLabelText(/^Modèle d'accès/), "free");
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
    await userEvent.selectOptions(screen.getByLabelText(/^Type de document/), "1");
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

describe("section des auteurs", () => {
  it("rattache un auteur avec son role", async () => {
    const { bodies } = stubApi();
    renderAt("/gestion/documents/77");

    await screen.findByRole("option", { name: /Aline NZE/ });
    await userEvent.selectOptions(screen.getByLabelText(/Auteur a rattacher/i), "9");
    await userEvent.selectOptions(screen.getByLabelText(/^Role/), "coauthor");
    await userEvent.click(screen.getByRole("button", { name: /rattacher/i }));

    await waitFor(() => {
      expect(bodies.at(-1)).toMatchObject({ author: 9, role: "coauthor" });
    });
  });

  it("propose un auteur qui n'a jamais ete publie", async () => {
    // Le registre staff voit tout le catalogue d'auteurs, contrairement a
    // l'endpoint public, qui n'en montre que les auteurs deja parus.
    stubApi();
    renderAt("/gestion/documents/77");

    expect(await screen.findByRole("option", { name: /Brice ONDO/ })).toBeInTheDocument();
  });

  it("detache un auteur deja rattache", async () => {
    const detachAuthor = vi.fn(() => new Response(null, { status: 204 }));
    stubApi({
      detachAuthor,
      detail: () =>
        new Response(
          JSON.stringify(
            staffDocument({
              authors: [{ id: 9, display_name: "Aline NZE", role: "author", position: 1 }]
            })
          )
        )
    });
    renderAt("/gestion/documents/77");

    await userEvent.click(await screen.findByRole("button", { name: /détacher Aline NZE/i }));

    await waitFor(() => expect(detachAuthor).toHaveBeenCalled());
  });
});

describe("section des droits", () => {
  it("enregistre une declaration et affiche son statut en attente de revue", async () => {
    const { bodies } = stubApi();
    renderAt("/gestion/documents/77");

    await userEvent.selectOptions(
      await screen.findByLabelText(/Type d'accord/i),
      "teacher_voluntary"
    );
    await userEvent.type(screen.getByLabelText(/Titulaire des droits/i), "Aline NZE");
    await userEvent.selectOptions(screen.getByLabelText(/Règle de retrait/i), "author_request");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer la déclaration/i }));

    await waitFor(() => {
      expect(bodies.at(-1)).toMatchObject({
        agreement_type: "teacher_voluntary",
        rights_holder_name: "Aline NZE",
        withdrawal_rule: "author_request"
      });
    });
    expect(await screen.findByText(/en attente de revue/i)).toBeInTheDocument();
  });

  it("reprend le modele d'acces du document, que le serveur exige identique", async () => {
    // Declarer une diffusion libre puis vendre le document par abonnement est
    // precisement la faute que la regle serveur empeche. L'ecran ne doit pas
    // permettre de la commettre par inadvertance.
    const { bodies } = stubApi();
    renderAt("/gestion/documents/77");

    await userEvent.selectOptions(
      await screen.findByLabelText(/Type d'accord/i),
      "open_license"
    );
    await userEvent.type(screen.getByLabelText(/Titulaire des droits/i), "BiblioGABON");
    await userEvent.selectOptions(screen.getByLabelText(/Règle de retrait/i), "author_request");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer la déclaration/i }));

    await waitFor(() => {
      expect(bodies.at(-1)).toMatchObject({ access_model: "free" });
    });
  });

  it("n'expose aucune commande d'approbation au deposant", async () => {
    // L'approbation appartient au moderateur. Meme desactive, un bouton
    // « approuver » dirait au deposant qu'il peut la demander ici, et la
    // separation des pouvoirs deviendrait une convention d'interface plutot
    // qu'une regle.
    stubApi({
      detail: () =>
        new Response(
          JSON.stringify(
            staffDocument({
              rights: {
                agreement_type: "teacher_voluntary",
                rights_holder_name: "Aline NZE",
                authorization_status: "pending_review",
                withdrawal_rule: "author_request",
                valid_for_publication: false
              }
            })
          )
        )
    });
    renderAt("/gestion/documents/77");
    await screen.findByLabelText(/Titulaire des droits/i);

    expect(screen.queryByRole("button", { name: /approuver/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /rejeter/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/reference d'audit/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/decision/i)).not.toBeInTheDocument();
  });
});

describe("robustesse de la fiche", () => {
  it("reste utilisable si le serveur n'annonce pas ses bornes de depot", async () => {
    // Un serveur plus ancien, ou une reponse tronquee par un intermediaire,
    // ne doit pas faire tomber la fiche entiere : lire `upload.max_bytes`
    // sans garde levait un TypeError et l'ecran devenait blanc.
    stubApi({
      index: () =>
        new Response(
          JSON.stringify({ name: "BiblioGABON staff API", version: "v1", schema: "/s/" })
        )
    });
    renderAt("/gestion/documents/77");

    expect(await screen.findByLabelText(/^Titre/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/fichier source/i)).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: /Traitement/ })).toBeInTheDocument();
  });
});

describe("fin de vie du document", () => {
  it("n'offre pas le retrait sur un brouillon", async () => {
    // Retirer ce qui n'a jamais paru n'a pas de sens ; proposer le geste
    // ferait croire qu'il produit quelque chose.
    stubApi();
    renderAt("/gestion/documents/77");
    await screen.findByLabelText(/^Titre/);

    expect(screen.queryByRole("button", { name: /retirer/i })).not.toBeInTheDocument();
  });

  it("exige un motif pour retirer un document publié", async () => {
    const { bodies } = stubApi({
      detail: () =>
        new Response(JSON.stringify(staffDocument({ publication_status: "published" })))
    });
    renderAt("/gestion/documents/77");

    await userEvent.click(await screen.findByRole("button", { name: /retirer du public/i }));
    await userEvent.click(screen.getByRole("button", { name: /confirmer le retrait/i }));

    expect(await screen.findByText(/motif est obligatoire/i)).toBeInTheDocument();
    expect(bodies.some((body) => typeof body === "object" && body && "reason" in body)).toBe(
      false
    );
  });

  it("retire avec le motif saisi", async () => {
    const { bodies } = stubApi({
      detail: () =>
        new Response(JSON.stringify(staffDocument({ publication_status: "published" })))
    });
    renderAt("/gestion/documents/77");

    await userEvent.click(await screen.findByRole("button", { name: /retirer du public/i }));
    await userEvent.type(
      screen.getByLabelText(/Motif du retrait/i),
      "Licence invalidée par l'éditeur."
    );
    await userEvent.click(screen.getByRole("button", { name: /confirmer le retrait/i }));

    await waitFor(() => {
      expect(bodies.at(-1)).toMatchObject({ reason: "Licence invalidée par l'éditeur." });
    });
  });

  it("rend le refus serveur d'un retrait interdit par la catégorie", async () => {
    stubApi({
      detail: () =>
        new Response(
          JSON.stringify(
            staffDocument({ publication_status: "published", category: "institutional_fund" })
          )
        ),
      withdraw: () =>
        new Response(
          JSON.stringify({
            error: {
              code: "permission_denied",
              message: "Vous ne pouvez pas retirer ce document.",
              field_errors: {}
            }
          }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        )
    });
    renderAt("/gestion/documents/77");

    await userEvent.click(await screen.findByRole("button", { name: /retirer du public/i }));
    await userEvent.type(screen.getByLabelText(/Motif du retrait/i), "Motif suffisant.");
    await userEvent.click(screen.getByRole("button", { name: /confirmer le retrait/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/ne pouvez pas retirer/);
  });
});

describe("journal d'audit", () => {
  // Le journal est une surface de modération : ces tests s'exécutent donc sous
  // un administrateur de contenu, comme à l'écran.
  const asModerator = { account: "content_admin" } as const;

  function event(overrides: Record<string, unknown> = {}) {
    return {
      id: 1,
      event_type: "document_withdrawn",
      summary: "Withdraw: Algebre lineaire",
      created_at: "2026-09-27T12:00:00Z",
      actor: { id: 7, display_name: "Moderation" },
      metadata: { reason: "Licence invalidée." },
      ...overrides
    };
  }

  it("rend qui, quoi, quand et pourquoi", async () => {
    stubApi({
      ...asModerator,
      audit: () =>
        new Response(
          JSON.stringify({ count: 1, next: null, previous: null, results: [event()] })
        )
    });
    renderAt("/gestion/documents/77");

    const trail = await screen.findByRole("list", { name: /journal/i });
    expect(within(trail).getByText(/Moderation/)).toBeInTheDocument();
    expect(within(trail).getByText(/Retrait/i)).toBeInTheDocument();
    expect(within(trail).getByText(/Licence invalidée/)).toBeInTheDocument();
  });

  it("ne suppose aucun champ présent dans les métadonnées filtrées", async () => {
    // Le serveur filtre `metadata` par liste blanche : un événement peut
    // arriver sans motif, et l'écran ne doit pas tomber pour autant.
    stubApi({
      ...asModerator,
      audit: () =>
        new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [event({ metadata: {}, actor: null })]
          })
        )
    });
    renderAt("/gestion/documents/77");

    const trail = await screen.findByRole("list", { name: /journal/i });
    expect(within(trail).getByText(/Système/i)).toBeInTheDocument();
  });

  it("affiche un type d'événement inconnu tel quel plutôt que de le masquer", async () => {
    stubApi({
      ...asModerator,
      audit: () =>
        new Response(
          JSON.stringify({
            count: 1,
            next: null,
            previous: null,
            results: [event({ event_type: "evenement_inedit" })]
          })
        )
    });
    renderAt("/gestion/documents/77");

    const trail = await screen.findByRole("list", { name: /journal/i });
    expect(within(trail).getByText("evenement_inedit")).toBeInTheDocument();
  });

  it("n'affiche ni clé de stockage ni URL dans le journal", async () => {
    stubApi({
      ...asModerator,
      audit: () =>
        new Response(
          JSON.stringify({ count: 1, next: null, previous: null, results: [event()] })
        )
    });
    renderAt("/gestion/documents/77");
    const trail = await screen.findByRole("list", { name: /journal/i });

    const rendered = trail.textContent ?? "";
    expect(rendered).not.toMatch(/\.pdf/i);
    expect(rendered).not.toMatch(/:\/\//);
    expect(rendered.toLowerCase()).not.toContain("storage");
  });
});

describe("ce que l'écran ne demande pas au serveur", () => {
  it("ne demande pas le journal d'audit à un déposant", async () => {
    // Le journal est réservé à la modération côté serveur. Le demander depuis
    // l'écran d'un enseignant enchaînait des 403 à chaque rendu. Une requête
    // dont on sait qu'elle échouera n'est pas une vérification, c'est du bruit
    // — dans la console, dans les journaux du serveur, et dans la tête de qui
    // diagnostique.
    const { calls } = stubApi();
    renderAt("/gestion/documents/77");
    await screen.findByLabelText(/^Titre/);

    expect(calls.filter((url) => url.pathname.endsWith("/audit/"))).toHaveLength(0);
    expect(screen.queryByRole("list", { name: /journal/i })).not.toBeInTheDocument();
  });

  it("refuse une déclaration de droits incomplète avant l'aller-retour", async () => {
    // Le serveur refuse aussi, mais avec « «  » n'est pas un choix valide »,
    // qui ne dit rien à personne.
    const { calls } = stubApi();
    renderAt("/gestion/documents/77");

    await userEvent.click(
      await screen.findByRole("button", { name: /enregistrer la déclaration/i })
    );

    expect(await screen.findByText(/Choisissez le type d'accord/i)).toBeInTheDocument();
    expect(calls.filter((url) => url.pathname.endsWith("/rights/"))).toHaveLength(0);
  });
});
