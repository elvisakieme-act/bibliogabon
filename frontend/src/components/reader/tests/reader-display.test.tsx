import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render as baseRender, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ReaderPage as ReaderPagePayload } from "@/api/types";
import { AuthProvider } from "@/auth/AuthProvider";
import { ReaderDisplayOptions } from "@/components/reader/ReaderDisplayOptions";
import { ReaderPage } from "@/components/reader/ReaderPage";
import { ReaderToolbar } from "@/components/reader/ReaderToolbar";
import {
  DEFAULT_ZOOM,
  nextZoom,
  readZoom,
  writeZoom,
  ZOOM_STEPS
} from "@/components/reader/readerPreferences";

/**
 * Barre, options et politique de copie du lecteur.
 *
 * Le lecteur n'a plus qu'un sens de lecture. Trois avaient été proposés, mais
 * les trois reposaient sur le même mécanisme — déplacer et agrandir une image
 * — et aucun des trois ne le servait : la molette zoomait au lieu de faire
 * défiler, et « horizontal » ne différait de « vertical » que par l'endroit
 * où les pages étaient posées dans le monde. Trois noms, un comportement.
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

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(new Blob(["image"], { type: "image/webp" })))
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function page(overrides: Partial<ReaderPagePayload> = {}): ReaderPagePayload {
  return {
    session_key: "cle",
    document_id: 1,
    version_id: 1,
    page_number: 1,
    page_count: 3,
    language_code: "fr",
    text: "Texte",
    words: [[0.1, 0.2, 0.3, 0.23, "Introduction"]],
    text_policy: "selectable",
    image: "/api/v1/reader/sessions/cle/pages/1/image/",
    iiif: null,
    ...overrides
  };
}

describe("barre du lecteur", () => {
  function renderToolbar(overrides: Partial<Parameters<typeof ReaderToolbar>[0]> = {}) {
    const props = {
      pageNumber: 2,
      pageCount: 5,
      onClose: vi.fn(),
      onOpenOptions: vi.fn(),
      ...overrides
    };
    render(<ReaderToolbar {...props} />);
    return props;
  }

  it("porte la sortie, la position et la marque, et rien d'autre", () => {
    renderToolbar();

    expect(screen.getByRole("button", { name: /Retour/i })).toBeInTheDocument();
    expect(screen.getByText("Page 2 sur 5")).toBeInTheDocument();
    expect(screen.getByLabelText("BiblioGABON")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Affichage/i })).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: "Page suivante" })).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Zoom" })).not.toBeInTheDocument();
  });

  it("annonce la position quand elle change", () => {
    // En défilement, la position change sans qu'aucun bouton n'ait été
    // actionné : sans `aria-live`, un lecteur d'écran ne l'apprend jamais.
    renderToolbar();

    expect(screen.getByText("Page 2 sur 5")).toHaveAttribute("aria-live", "polite");
  });

  it("ne fait pas de la marque une seconde sortie", () => {
    renderToolbar();

    expect(screen.queryByRole("link", { name: "BiblioGABON" })).not.toBeInTheDocument();
  });

  it("ouvre les options d'affichage", async () => {
    const props = renderToolbar();
    await userEvent.click(screen.getByRole("button", { name: /Affichage/i }));

    expect(props.onOpenOptions).toHaveBeenCalled();
  });

  it("garde la sortie visible en permanence", async () => {
    const props = renderToolbar();
    await userEvent.click(screen.getByRole("button", { name: /Retour/i }));

    expect(props.onClose).toHaveBeenCalled();
  });
});

describe("options d'affichage", () => {
  function renderOptions(overrides: Partial<Parameters<typeof ReaderDisplayOptions>[0]> = {}) {
    const props = {
      open: true,
      zoom: DEFAULT_ZOOM,
      onClose: vi.fn(),
      onZoomChange: vi.fn(),
      ...overrides
    };
    render(<ReaderDisplayOptions {...props} />);
    return props;
  }

  it("ne propose plus de sens de lecture", () => {
    renderOptions();

    expect(screen.queryByRole("button", { name: /Double page/ })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Défilement horizontal/ })
    ).not.toBeInTheDocument();
  });

  it("règle la taille de la page", async () => {
    const props = renderOptions();
    await userEvent.click(screen.getByRole("button", { name: "Agrandir" }));

    expect(props.onZoomChange).toHaveBeenCalledWith(1);
  });

  it("bloque le zoom aux extrémités de l'échelle", () => {
    // Sans cela, un lecteur peut continuer à cliquer sans rien obtenir.
    renderOptions({ zoom: ZOOM_STEPS[ZOOM_STEPS.length - 1] });

    expect(screen.getByRole("button", { name: "Agrandir" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Réduire" })).toBeEnabled();
  });
});

describe("échelle de zoom", () => {
  it("avance et recule dans l'échelle", () => {
    expect(nextZoom(1, 1)).toBe(1.25);
    expect(nextZoom(1, -1)).toBe(0.9);
  });

  it("ne sort jamais de l'échelle", () => {
    expect(nextZoom(ZOOM_STEPS[ZOOM_STEPS.length - 1], 1)).toBe(
      ZOOM_STEPS[ZOOM_STEPS.length - 1]
    );
    expect(nextZoom(ZOOM_STEPS[0], -1)).toBe(ZOOM_STEPS[0]);
  });
});

describe("mémoire du zoom", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("retrouve le réglage d'une lecture à l'autre", () => {
    writeZoom(1.5);

    expect(readZoom()).toBe(1.5);
  });

  it("ignore un réglage corrompu plutôt que d'ouvrir un lecteur cassé", () => {
    window.localStorage.setItem("bibliogabon.lecteur", "{ pas du json");

    expect(readZoom()).toBe(DEFAULT_ZOOM);
  });

  it("refuse un zoom hors de l'échelle", () => {
    // Une valeur arbitraire rendrait la page illisible ou invisible, et le
    // lecteur n'aurait aucun moyen de revenir en arrière.
    window.localStorage.setItem("bibliogabon.lecteur", JSON.stringify({ zoom: 42 }));

    expect(readZoom()).toBe(DEFAULT_ZOOM);
  });
});

describe("politique de copie", () => {
  it("laisse copier une ressource sous licence ouverte", async () => {
    render(<ReaderPage title="Ressource" page={page({ text_policy: "selectable" })} />);

    expect((await screen.findByText("Introduction")).parentElement).toHaveClass("select-text");
  });

  it("empêche la copie d'un document sous accord restrictif", async () => {
    render(<ReaderPage title="Mémoire" page={page({ text_policy: "protected" })} />);

    expect((await screen.findByText("Introduction")).parentElement).toHaveClass("select-none");
  });

  it("garde le texte lisible par un lecteur d'écran même quand la copie est bloquée", async () => {
    // C'est le seul point de ce sujet sans arbitrage : `user-select: none`
    // dissuade la copie sans rien retirer à l'accessibilité.
    render(<ReaderPage title="Mémoire" page={page({ text_policy: "protected" })} />);

    expect(await screen.findByText("Introduction")).toBeInTheDocument();
  });

  it("n'affiche aucune couche texte quand le serveur la retient", () => {
    // Une clause de confidentialité : le serveur n'envoie pas les positions.
    render(
      <ReaderPage title="Confidentiel" page={page({ text_policy: "withheld", words: [] })} />
    );

    expect(screen.queryByText("Introduction")).not.toBeInTheDocument();
  });
});

describe("amplitude du zoom", () => {
  it("descend assez bas pour voir une page entière", () => {
    // S'arrêter à 75 % interdisait la vue d'ensemble : repérer un tableau,
    // situer une figure, juger la mise en page avant de lire.
    expect(ZOOM_STEPS[0]).toBeLessThanOrEqual(0.5);
  });

  it("monte assez haut pour lire une note de bas de page", () => {
    expect(ZOOM_STEPS[ZOOM_STEPS.length - 1]).toBeGreaterThanOrEqual(3);
  });

  it("se resserre autour de la taille d'origine", () => {
    // C'est à 100 % qu'on ajuste ; aux extrémités, on cherche un ordre de
    // grandeur. Des paliers réguliers obligeraient à cliquer six fois pour
    // passer de 90 % à 125 %.
    const index = ZOOM_STEPS.indexOf(1 as never);
    const autour = ZOOM_STEPS[index + 1] - ZOOM_STEPS[index - 1];
    const auBout = ZOOM_STEPS[ZOOM_STEPS.length - 1] - ZOOM_STEPS[ZOOM_STEPS.length - 3];

    expect(autour).toBeLessThan(auBout);
  });
});
