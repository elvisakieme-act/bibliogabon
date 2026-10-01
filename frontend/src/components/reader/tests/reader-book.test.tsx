import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render as baseRender, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/auth/AuthProvider";
import { ReaderBookView } from "@/components/reader/ReaderBookView";
import type { IiifManifest } from "@/features/reader/manifest";

/**
 * Le document en double page.
 *
 * Sa mécanique est la sienne : un état, une double page, une transition. Ce
 * n'est pas un réglage du défilement — faire partager un mécanisme à trois
 * modes les avait cassés tous les trois.
 *
 * jsdom ne met rien en page : ce qui se vérifie ici est la **structure** —
 * combien de pages, laquelle, et ce que fait chaque geste. L'ajustement à la
 * hauteur et le creux de reliure se jugent à l'écran.
 */
function manifest(pages = [1, 2, 3, 4, 5]): IiifManifest {
  return {
    id: "http://localhost/manifest",
    label: { fr: ["Document"] },
    items: pages.map((number) => ({
      id: `http://localhost/api/v1/reader/sessions/x/canvas/${number}`,
      width: 2480,
      height: 3508,
      items: [
        {
          items: [
            {
              body: {
                service: [
                  {
                    id: `http://localhost/api/v1/reader/sessions/x/pages/${number}/iiif`,
                    type: "ImageService3",
                    profile: "level0",
                    width: 2480,
                    height: 3508,
                    tiles: [{ width: 512, scaleFactors: [1, 2] }],
                    sizes: [
                      { width: 2480, height: 3508 },
                      { width: 620, height: 877 }
                    ]
                  }
                ]
              }
            }
          ]
        }
      ]
    }))
  };
}

function render(pageNumber: number, onVisiblePage = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } }
  });
  const result = baseRender(
    <AuthProvider>
      <QueryClientProvider client={client}>
        <ReaderBookView
          sessionKey="x"
          manifest={manifest()}
          zoom={1}
          pageNumber={pageNumber}
          onVisiblePage={onVisiblePage}
        />
      </QueryClientProvider>
    </AuthProvider>
  );
  return { ...result, onVisiblePage };
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

describe("double page", () => {
  it("ouvre la couverture seule", () => {
    const { container } = render(1);

    expect(container.querySelectorAll("[data-page]")).toHaveLength(1);
    expect(container.querySelector('[data-page="1"]')).toBeInTheDocument();
  });

  it("montre deux pages ensuite", () => {
    const { container } = render(2);

    expect(container.querySelectorAll("[data-page]")).toHaveLength(2);
    expect(container.querySelector('[data-page="2"]')).toBeInTheDocument();
    expect(container.querySelector('[data-page="3"]')).toBeInTheDocument();
  });

  it("montre la même double qu'on arrive par la page de gauche ou de droite", () => {
    // Un lien de reprise sur la page 3 doit ouvrir la double (2,3), pas
    // décaler le document d'une page.
    const { container } = render(3);

    expect(container.querySelector('[data-page="2"]')).toBeInTheDocument();
    expect(container.querySelector('[data-page="3"]')).toBeInTheDocument();
  });

  it("tourne d'une double, pas d'une page", () => {
    // Avancer d'une page désynchroniserait l'appariement : la page qui était
    // à droite passerait à gauche, et tout le document se lirait décalé.
    const { onVisiblePage } = render(2);
    onVisiblePage.mockClear();

    fireEvent.click(screen.getAllByRole("button", { name: "Page suivante" })[0]);

    expect(onVisiblePage).toHaveBeenCalledWith(4);
  });

  it("tourne au clavier", () => {
    const { container, onVisiblePage } = render(2);
    onVisiblePage.mockClear();

    fireEvent.keyDown(container.querySelector("[aria-label=Document]")!, {
      key: "ArrowRight"
    });

    expect(onVisiblePage).toHaveBeenCalledWith(4);
  });

  it("revient en arrière au clavier", () => {
    const { container, onVisiblePage } = render(4);
    onVisiblePage.mockClear();

    fireEvent.keyDown(container.querySelector("[aria-label=Document]")!, {
      key: "ArrowLeft"
    });

    expect(onVisiblePage).toHaveBeenCalledWith(2);
  });

  it("se laisse parcourir au clavier sans clic préalable", () => {
    // Sans `tabindex`, les flèches ne font rien tant qu'on n'a pas cliqué
    // dans la page.
    const { container } = render(2);

    expect(container.querySelector("[aria-label=Document]")).toHaveAttribute("tabindex", "0");
  });

  it("ne tourne pas au-delà du document", () => {
    const { onVisiblePage } = render(4);
    onVisiblePage.mockClear();

    // La dernière double est (4,5) : il n'y a pas de suivante. La flèche
    // reste en place mais désactivée — la retirer ferait sauter la mise en
    // page au dernier tour.
    expect(screen.getByRole("button", { name: "Page suivante" })).toBeDisabled();
    // Les coins, eux, disparaissent : un coin qu'on peut saisir sans que
    // rien ne se passe est une promesse que le document ne tient pas.
    expect(screen.getAllByRole("button", { name: "Page suivante" })).toHaveLength(1);
    expect(onVisiblePage).not.toHaveBeenCalled();
  });

  it("offre les coins de page en plus des flèches", async () => {
    // On saisit le haut ou le bas d'une page et on la tire, comme on tourne
    // une feuille. Deux coins de chaque côté, plus la flèche.
    render(2);

    expect(await screen.findAllByRole("button", { name: "Page suivante" })).toHaveLength(3);
    expect(screen.getAllByRole("button", { name: "Page précédente" })).toHaveLength(3);
  });

  it("ne tourne par un coin qu'au-delà d'un geste franc", () => {
    // Un simple clic sur un coin tournerait la page pendant qu'on veut
    // seulement déplacer la vue, et le lecteur perdrait sa place.
    const { onVisiblePage } = render(2);
    onVisiblePage.mockClear();
    const coin = screen.getAllByRole("button", { name: "Page suivante" })[1];

    fireEvent.pointerDown(coin, { pointerId: 1, clientX: 400 });
    fireEvent.pointerMove(coin, { pointerId: 1, clientX: 380 });
    expect(onVisiblePage).not.toHaveBeenCalled();

    fireEvent.pointerMove(coin, { pointerId: 1, clientX: 300 });
    expect(onVisiblePage).toHaveBeenCalledWith(4);
  });
});

describe("écran étroit", () => {
  it("ne montre qu'une page, et continue de tourner", async () => {
    // Deux pages sur 390 px ne sont pas lisibles, et un mode qui prétend
    // l'être ment. Le geste reste celui du livre : on tourne, on ne défile
    // pas.
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: true,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false
    }));

    const onVisiblePage = vi.fn();
    const { container } = render(2, onVisiblePage);

    expect(container.querySelectorAll("[data-page]")).toHaveLength(1);

    onVisiblePage.mockClear();
    await userEvent.click(screen.getAllByRole("button", { name: "Page suivante" })[0]);

    // Une page à la fois : on avance de 1, pas de 2.
    expect(onVisiblePage).toHaveBeenCalledWith(3);
  });
});
