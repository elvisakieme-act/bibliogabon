import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthProvider } from "@/auth/AuthProvider";
import { tokenStore } from "@/auth/tokenStore";
import { render as baseRender, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ReaderPage as ReaderPagePayload } from "@/api/types";
import { ReaderPage } from "@/components/reader/ReaderPage";
import { reflowExtractedText } from "@/components/reader/reflowExtractedText";

/**
 * Fidélité de lecture.
 *
 * Le lecteur servait le texte extrait, à plat : un mémoire y perdait ses
 * titres, ses tableaux, ses figures et ses formules, et les retours à la ligne
 * du PDF étaient conservés tels quels — si bien qu'un téléphone repliait le
 * texte deux fois.
 *
 * L'image de la page était pourtant produite à chaque ingestion, et jamais
 * servie.
 */

/**
 * Rendu d'un composant du lecteur.
 *
 * Le lecteur récupère l'image de la page avec son jeton — une balise `<img>`
 * ne peut pas porter d'en-tête d'authentification. Il lui faut donc un
 * fournisseur de requêtes, et un `fetch` qui réponde une image.
 */
function render(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } }
  });
  return baseRender(
    <AuthProvider>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </AuthProvider>
  );
}

function respond(input: RequestInfo | URL, unusedInit?: RequestInit) {
  void unusedInit;
  // Le fournisseur d'authentification interroge le profil au montage :
  // lui répondre une image invaliderait la session, et le jeton ne partirait
  // jamais avec la requête d'image.
  if (String(input).includes("/api/v1/me/")) {
    return new Response(JSON.stringify({ id: 1, email: "lecteur@example.ga" }), {
      headers: { "Content-Type": "application/json" }
    });
  }
  return new Response(new Blob([String(input)], { type: "image/webp" }));
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => respond(input))
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  tokenStore.clear();
});

function page(overrides: Partial<ReaderPagePayload> = {}): ReaderPagePayload {
  return {
    session_key: "550e8400-e29b-41d4-a716-446655440000",
    document_id: 1,
    version_id: 1,
    page_number: 2,
    page_count: 5,
    language_code: "fr",
    text: "Introduction générale\nLa littérature gabonaise s'écrit dans un\nrapport tendu au passé.\n2",
    words: [],
    text_policy: "selectable",
    image: null,
    ...overrides
  };
}

describe("page rendue", () => {
  it("affiche l'image de la page quand elle existe", async () => {
    const { container } = render(
      <ReaderPage
        title="Thèse"
        page={page({ image: "/api/v1/reader/sessions/abc/pages/2/image/" })}
      />
    );

    // L'image est récupérée avec le jeton puis remise au navigateur sous
    // forme de `blob:` — une balise `<img src>` ne peut pas porter d'en-tête
    // d'authentification, et c'est ce qui faisait échouer toutes les pages
    // d'un lecteur connecté.
    await waitFor(() => expect(container.querySelector("img")).not.toBeNull());
    expect(container.querySelector("img")?.getAttribute("src")).toMatch(/^blob:/);
  });

  it("superpose une couche texte sélectionnable", async () => {
    // Sans elle, l'image serait fidèle et muette : ni sélection, ni recherche
    // dans la page, ni lecture d'écran.
    render(
      <ReaderPage
        title="Thèse"
        page={page({
          image: "/api/v1/reader/sessions/abc/pages/2/image/",
          words: [
            [0.1, 0.2, 0.3, 0.23, "Introduction"],
            [0.32, 0.2, 0.45, 0.23, "générale"]
          ]
        })}
      />
    );

    expect(await screen.findByText("Introduction")).toBeInTheDocument();
    expect(screen.getByText("générale")).toBeInTheDocument();
  });

  it("positionne chaque mot en pourcentages, jamais en pixels", async () => {
    // Le serveur stocke des fractions précisément pour que la couche suive
    // l'image à tout zoom. Des pixels ici annuleraient cette propriété.
    render(
      <ReaderPage
        title="Thèse"
        page={page({
          image: "/api/v1/reader/sessions/abc/pages/2/image/",
          words: [[0.25, 0.5, 0.75, 0.54, "mot"]]
        })}
      />
    );

    const word = await screen.findByText("mot");
    expect(word.style.left).toBe("25%");
    expect(word.style.top).toBe("50%");
    expect(word.style.width).toBe("50%");
  });

  it("n'annonce pas l'image aux lecteurs d'écran", async () => {
    // Le texte qui décrit l'image est juste au-dessus, dans la couche
    // transparente : une alternative le répéterait à chaque page.
    const { container } = render(
      <ReaderPage
        title="Thèse"
        page={page({ image: "/api/v1/reader/sessions/abc/pages/2/image/" })}
      />
    );

    await waitFor(() => expect(container.querySelector("img")).not.toBeNull());
    expect(container.querySelector("img")).toHaveAttribute("alt", "");
  });

  it("demande l'image avec le jeton d'authentification", async () => {
    // Le défaut que les tests ne pouvaient pas voir : une balise `<img src>`
    // n'envoie aucun en-tête, et le serveur refusait donc chaque page d'un
    // lecteur connecté. Il a fallu regarder l'écran dans un vrai navigateur
    // pour s'en apercevoir.
    tokenStore.set({ access: "jeton-de-test", refresh: "rafraichissement" });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
      respond(input, init)
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReaderPage
        title="Thèse"
        page={page({ image: "/api/v1/reader/sessions/abc/pages/2/image/" })}
      />
    );

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes("/pages/2/image/"))
      ).toBe(true)
    );
    const imageCalls = fetchMock.mock.calls.filter(([candidate]) =>
      String(candidate).includes("/pages/2/image/")
    );
    // Une seule requête : partir avant que la session soit hydratée
    // provoquerait un 403 puis un second appel, et le lecteur afficherait une
    // erreur entre les deux.
    expect(imageCalls).toHaveLength(1);
    const [url, init] = imageCalls[0];
    expect(String(url)).toContain("/api/v1/reader/sessions/abc/pages/2/image/");
    // L'en-tête, pas seulement l'adresse : c'est lui qui manquait, et une
    // vérification de l'adresse seule laisserait le défaut revenir.
    expect((init?.headers as Record<string, string>)?.Authorization).toBe(
      "Bearer jeton-de-test"
    );
  });

  it("libère l'adresse blob quand la page disparaît", async () => {
    // Un document de 157 pages en défilement continu : sans révocation, le
    // navigateur garde chaque image en mémoire jusqu'à la fermeture de
    // l'onglet.
    const revoked = (globalThis as { __revokedObjectUrls?: string[] }).__revokedObjectUrls;
    const before = revoked?.length ?? 0;

    const { container, unmount } = render(
      <ReaderPage
        title="Thèse"
        page={page({ image: "/api/v1/reader/sessions/abc/pages/2/image/" })}
      />
    );
    await waitFor(() => expect(container.querySelector("img")).not.toBeNull());
    const source = container.querySelector("img")?.getAttribute("src");

    unmount();

    expect(revoked?.slice(before)).toContain(source);
  });

  it("dit pourquoi la page manque plutôt que d'afficher un vide", async () => {
    // Le cadre garde le format d'une page même sans image : sans cela,
    // l'article n'avait aucune hauteur et le lecteur voyait un écran vide,
    // sans rien pour comprendre.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 403 }))
    );

    render(
      <ReaderPage
        title="Thèse"
        page={page({ image: "/api/v1/reader/sessions/abc/pages/2/image/" })}
      />
    );

    expect(await screen.findByText(/n'a pas pu être affichée/)).toBeInTheDocument();
  });

  it("retombe sur le texte quand la page n'a pas de rendu", () => {
    const { container } = render(<ReaderPage title="Thèse" page={page()} />);

    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(/littérature gabonaise/)).toBeInTheDocument();
  });
});

describe("texte de repli", () => {
  it("recolle les lignes d'un même paragraphe", () => {
    // Le défaut d'origine : les retours à la ligne du PDF étaient ceux de sa
    // mise en page, pas ceux du propos.
    const paragraphs = reflowExtractedText(
      "La littérature gabonaise s'écrit dans un\nrapport tendu au passé."
    );

    expect(paragraphs).toEqual([
      "La littérature gabonaise s'écrit dans un rapport tendu au passé."
    ]);
  });

  it("garde un titre séparé du paragraphe qui le suit", () => {
    const paragraphs = reflowExtractedText(
      "Introduction générale\nLa littérature gabonaise s'écrit dans un\nrapport tendu au passé."
    );

    expect(paragraphs).toHaveLength(2);
    expect(paragraphs[0]).toBe("Introduction générale");
  });

  it("garde les entrées d'une liste séparées", () => {
    const paragraphs = reflowExtractedText(
      "Le corpus comprend\n— quatorze romans\n— deux recueils"
    );

    expect(paragraphs).toHaveLength(3);
  });

  it("retire le numéro de page isolé", () => {
    // C'est un artefact de mise en page, pas une phrase à lire — et il
    // apparaissait tel quel au milieu du texte.
    const paragraphs = reflowExtractedText("Dernière phrase du paragraphe.\n2", 2);

    expect(paragraphs).toEqual(["Dernière phrase du paragraphe."]);
  });

  it("ne retire pas un nombre qui n'est pas le numéro de page", () => {
    const paragraphs = reflowExtractedText("Dernière phrase.\n1990", 2);

    expect(paragraphs).toContain("1990");
  });
});
