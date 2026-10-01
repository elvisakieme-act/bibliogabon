import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render as baseRender } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/auth/AuthProvider";
import { ReaderViewport } from "@/components/reader/ReaderViewport";
import type { IiifManifest } from "@/features/reader/manifest";

/**
 * Le document en défilement vertical.
 *
 * Ce que jsdom peut vérifier ici est la **structure** : un conteneur qui
 * défile, une page par canevas, et une largeur qui suit le zoom. Il ne met
 * rien en page, donc il ne verra jamais un chevauchement ni un plafond
 * atteint — ces défauts-là se trouvent en regardant l'écran, et les deux
 * derniers du lecteur ont été trouvés ainsi.
 */
function manifest(pages = [1, 2, 3]): IiifManifest {
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
                    tiles: [{ width: 512, scaleFactors: [1, 2, 4, 8] }],
                    sizes: [
                      { width: 2480, height: 3508 },
                      { width: 1240, height: 1754 },
                      { width: 620, height: 877 },
                      { width: 310, height: 439 }
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

function render(zoom: number) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } }
  });
  return baseRender(
    <AuthProvider>
      <QueryClientProvider client={client}>
        <ReaderViewport
          sessionKey="x"
          manifest={manifest()}
          zoom={zoom}
          pageNumber={1}
          onVisiblePage={vi.fn()}
        />
      </QueryClientProvider>
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

describe("défilement vertical", () => {
  it("défile vraiment, et au clavier", () => {
    // Un conteneur qui défile donne la molette, le pavé tactile, le doigt,
    // les flèches, la barre de défilement et la touche Origine sans qu'on
    // écrive une ligne pour chacun. La version précédente déplaçait une image
    // : la molette y zoomait.
    const { container } = render(1);
    const document_ = container.querySelector("[aria-label=Document]");

    expect(document_).toHaveClass("overflow-y-auto");
    // Sans `tabindex`, les flèches ne défilent pas tant qu'on n'a pas cliqué
    // dans la page.
    expect(document_).toHaveAttribute("tabindex", "0");
  });

  it("rend une page par canevas", () => {
    const { container } = render(1);

    expect(container.querySelectorAll("[data-page]")).toHaveLength(3);
  });

  it("agrandit réellement, sans plafonner à la largeur du conteneur", () => {
    // Écrite `min(100%, 52rem * zoom)`, la largeur plafonnait à celle du
    // conteneur : au-delà d'environ 170 % sur un écran large, le zoom ne
    // faisait plus rien. La référence doit être bornée **avant** d'être
    // multipliée, pas après.
    const largeur = (zoom: number) =>
      parseFloat(
        (
          render(zoom).container.querySelector(
            "[aria-label=Document] > div > div"
          ) as HTMLElement
        ).style.width
      );

    expect(largeur(3)).toBeCloseTo(largeur(1) * 3, 0);
    expect(largeur(0.5)).toBeCloseTo(largeur(1) * 0.5, 0);
  });
});
