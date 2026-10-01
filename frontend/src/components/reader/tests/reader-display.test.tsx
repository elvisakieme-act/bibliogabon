import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthProvider } from "@/auth/AuthProvider";
import { fireEvent, render as baseRender, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ReaderPage as ReaderPagePayload } from "@/api/types";
import { ReaderPage } from "@/components/reader/ReaderPage";
import { ReaderDisplayOptions } from "@/components/reader/ReaderDisplayOptions";
import { ReaderPageTurn } from "@/components/reader/ReaderPageTurn";
import { ReaderToolbar } from "@/components/reader/ReaderToolbar";
import {
  DEFAULT_MODE,
  DEFAULT_ZOOM,
  nextZoom,
  readPreferences,
  writePreferences,
  ZOOM_STEPS
} from "@/components/reader/readerPreferences";

/**
 * Options d'affichage du lecteur.
 *
 * Un lecteur qui n'offre qu'un seul sens de défilement impose l'usage : le
 * vertical convient à un écran d'ordinateur, l'horizontal au geste du
 * téléphone, la double page à qui consulte un ouvrage plutôt qu'il ne le lit
 * en continu.
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
    // Une barre qui expose tous les réglages les met au même rang que la
    // lecture, et n'en laisse plus la place sur un téléphone.
    renderToolbar();

    expect(screen.getByRole("button", { name: /Retour/i })).toBeInTheDocument();
    expect(screen.getByText("Page 2 sur 5")).toBeInTheDocument();
    expect(screen.getByLabelText("BiblioGABON")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Affichage/i })).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: "Page suivante" })).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Zoom" })).not.toBeInTheDocument();
  });

  it("annonce la position quand elle change", () => {
    // En défilement continu, la position change sans qu'aucun bouton n'ait
    // été actionné : sans `aria-live`, un lecteur d'écran ne l'apprend jamais.
    renderToolbar();

    expect(screen.getByText("Page 2 sur 5")).toHaveAttribute("aria-live", "polite");
  });

  it("ne fait pas de la marque une seconde sortie", () => {
    // Un logo cliquable quitterait la lecture sans que rien l'annonce, en
    // concurrence du bouton « Retour ».
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
      mode: DEFAULT_MODE,
      zoom: DEFAULT_ZOOM,
      onClose: vi.fn(),
      onModeChange: vi.fn(),
      onZoomChange: vi.fn(),
      ...overrides
    };
    render(<ReaderDisplayOptions {...props} />);
    return props;
  }

  it("propose les trois sens de lecture", () => {
    renderOptions();

    expect(screen.getByRole("button", { name: /Défilement vertical/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Défilement horizontal/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Double page/ })).toBeInTheDocument();
  });

  it("annonce le sens actif aux technologies d'assistance", () => {
    // `aria-pressed` et non une simple couleur : un utilisateur de lecteur
    // d'écran doit savoir dans quel mode il se trouve.
    renderOptions({ mode: "livre" });

    expect(screen.getByRole("button", { name: /Double page/ })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByRole("button", { name: /Défilement vertical/ })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  it("change de sens quand on le demande", async () => {
    const props = renderOptions();
    await userEvent.click(screen.getByRole("button", { name: /Défilement horizontal/ }));

    expect(props.onModeChange).toHaveBeenCalledWith("horizontal");
  });

  it("bloque le zoom aux extrémités de l'échelle", () => {
    renderOptions({ zoom: ZOOM_STEPS[ZOOM_STEPS.length - 1] });

    expect(screen.getByRole("button", { name: "Agrandir" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Réduire" })).toBeEnabled();
  });
});

describe("passage d'une page à l'autre", () => {
  function renderTurn(overrides: Partial<Parameters<typeof ReaderPageTurn>[0]> = {}) {
    const props = {
      mode: "horizontal" as const,
      canGoBack: true,
      canGoForward: true,
      onPrevious: vi.fn(),
      onNext: vi.fn(),
      ...overrides
    };
    render(<ReaderPageTurn {...props} />);
    return props;
  }

  it("n'affiche aucune flèche en défilement vertical", () => {
    // Les pages s'y enchaînent : une flèche « suivante » proposerait un geste
    // que le défilement fait déjà, et deux façons de faire la même chose
    // désignent un écran qui n'a pas choisi.
    renderTurn({ mode: "vertical" });

    expect(screen.queryByRole("button", { name: "Page suivante" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Page précédente" })).not.toBeInTheDocument();
  });

  it("place les flèches dans le document en mode horizontal", () => {
    renderTurn({ mode: "horizontal" });

    expect(screen.getByRole("button", { name: "Page suivante" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Page précédente" })).toBeInTheDocument();
  });

  it("ajoute les coins de page en mode livre", () => {
    // On saisit le haut ou le bas d'une page et on la tire : quatre coins,
    // deux de chaque côté.
    renderTurn({ mode: "livre" });

    expect(screen.getAllByRole("button", { name: "Page suivante" })).toHaveLength(3);
    expect(screen.getAllByRole("button", { name: "Page précédente" })).toHaveLength(3);
  });

  it("ne tourne la page qu'au-delà d'un geste franc", () => {
    // Un simple clic sur un coin tournerait la page pendant qu'on veut
    // seulement déplacer la vue, et le lecteur perdrait sa place.
    const props = renderTurn({ mode: "livre" });
    const corner = screen.getAllByRole("button", { name: "Page suivante" })[1];

    fireEvent.pointerDown(corner, { pointerId: 1, clientX: 400 });
    fireEvent.pointerMove(corner, { pointerId: 1, clientX: 390 });
    expect(props.onNext).not.toHaveBeenCalled();

    fireEvent.pointerMove(corner, { pointerId: 1, clientX: 320 });
    expect(props.onNext).toHaveBeenCalledTimes(1);
  });

  it("ne tourne pas dans le mauvais sens", () => {
    const props = renderTurn({ mode: "livre" });
    const corner = screen.getAllByRole("button", { name: "Page suivante" })[1];

    fireEvent.pointerDown(corner, { pointerId: 1, clientX: 400 });
    fireEvent.pointerMove(corner, { pointerId: 1, clientX: 500 });

    expect(props.onNext).not.toHaveBeenCalled();
  });

  it("retire la flèche quand il n'y a plus de page", () => {
    renderTurn({ mode: "horizontal", canGoForward: false });

    expect(screen.getByRole("button", { name: "Page suivante" })).toBeDisabled();
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

describe("mémoire des préférences", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("retrouve le réglage du lecteur d'une lecture à l'autre", () => {
    writePreferences({ mode: "livre", zoom: 1.5 });

    expect(readPreferences()).toEqual({ mode: "livre", zoom: 1.5 });
  });

  it("ignore un réglage corrompu plutôt que d'ouvrir un lecteur cassé", () => {
    window.localStorage.setItem("bibliogabon.lecteur", "{ pas du json");

    expect(readPreferences()).toEqual({ mode: DEFAULT_MODE, zoom: DEFAULT_ZOOM });
  });

  it("refuse un zoom hors de l'échelle", () => {
    // Une valeur arbitraire rendrait la page illisible ou invisible, et le
    // lecteur n'aurait aucun moyen de revenir en arrière.
    window.localStorage.setItem(
      "bibliogabon.lecteur",
      JSON.stringify({ mode: "vertical", zoom: 42 })
    );

    expect(readPreferences().zoom).toBe(DEFAULT_ZOOM);
  });

  it("refuse un sens de défilement inconnu", () => {
    window.localStorage.setItem(
      "bibliogabon.lecteur",
      JSON.stringify({ mode: "diagonal", zoom: 1 })
    );

    expect(readPreferences().mode).toBe(DEFAULT_MODE);
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
