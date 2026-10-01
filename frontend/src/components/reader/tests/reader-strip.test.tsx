import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render as baseRender, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/auth/AuthProvider";
import { ReaderStripView } from "@/components/reader/ReaderStripView";
import type { IiifManifest } from "@/features/reader/manifest";

/**
 * Le document en défilement horizontal.
 *
 * Ce que jsdom peut vérifier est la **structure** et les **gestes** : combien
 * de pages, ce qui commande leur taille, ce que fait chaque flèche et chaque
 * touche, et où vivent les commandes. Il ne met rien en page : l'ajustement à
 * la hauteur et l'arrêt sur une page se jugent à l'écran, et les derniers
 * défauts du lecteur ont tous été trouvés ainsi.
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

function render(pageNumber: number, { zoom = 1, pages = [1, 2, 3] } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } }
  });
  const onVisiblePage = vi.fn();
  const result = baseRender(
    <AuthProvider>
      <QueryClientProvider client={client}>
        <ReaderStripView
          sessionKey="x"
          manifest={manifest(pages)}
          zoom={zoom}
          pageNumber={pageNumber}
          onVisiblePage={onVisiblePage}
        />
      </QueryClientProvider>
    </AuthProvider>
  );
  const scroller = result.container.querySelector("[aria-label=Document]") as HTMLElement;
  return { ...result, onVisiblePage, scroller };
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

describe("défilement horizontal", () => {
  it("défile vraiment, et s'arrête sur une page", () => {
    // C'est un conteneur qui défile — la molette, le pavé tactile, le doigt et
    // la barre de défilement viennent avec. L'arrêt sur une page est ce qui en
    // fait un mode de lecture : une bande immobilisée à cheval sur deux pages
    // ne se lit pas.
    const { scroller } = render(1);

    expect(scroller).toHaveClass("overflow-auto");
    expect(scroller).toHaveClass("snap-x");
    expect(scroller).toHaveClass("snap-mandatory");
    // Sans `tabindex`, le clavier ne fait rien tant qu'on n'a pas cliqué dans
    // la page.
    expect(scroller).toHaveAttribute("tabindex", "0");
  });

  it("rend une page par canevas", () => {
    const { container } = render(1);

    expect(container.querySelectorAll("[data-page]")).toHaveLength(3);
  });

  it("donne à chaque page le rapport du manifeste", () => {
    // C'est ce qui distingue ce mode du défilement vertical : là-bas une largeur
    // de lecture est imposée et la page dépasse en bas ; ici la page tient
    // entière, et sa largeur découle de son rapport. La hauteur, elle, est
    // calculée sur la place mesurée — ce que jsdom ne mesure pas, et que
    // `stripLayout` éprouve de son côté.
    const bande = render(1).scroller.querySelector(":scope > div") as HTMLElement;
    const page = bande.querySelector(":scope > div") as HTMLElement;

    expect(page.style.aspectRatio).toBe("2480 / 3508");
    expect(page).toHaveClass("snap-center");
    // La bande n'impose pas de hauteur : des pages plus hautes que l'écran, une
    // fois agrandies, doivent la faire grandir plutôt que déborder vers le haut,
    // où le défilement ne va pas.
    expect(bande.style.height).toBe("");
    expect(bande).toHaveClass("items-center");
  });

  it("avance d'une page par la flèche", () => {
    const { onVisiblePage } = render(1);
    onVisiblePage.mockClear();

    fireEvent.click(screen.getByRole("button", { name: "Page suivante" }));

    expect(onVisiblePage).toHaveBeenCalledWith(2);
  });

  it("revient d'une page par la flèche", () => {
    const { onVisiblePage } = render(3);
    onVisiblePage.mockClear();

    fireEvent.click(screen.getByRole("button", { name: "Page précédente" }));

    expect(onVisiblePage).toHaveBeenCalledWith(2);
  });

  it("avance et recule au clavier", () => {
    const { onVisiblePage, scroller } = render(2);

    onVisiblePage.mockClear();
    fireEvent.keyDown(scroller, { key: "ArrowRight" });
    expect(onVisiblePage).toHaveBeenCalledWith(3);

    onVisiblePage.mockClear();
    fireEvent.keyDown(scroller, { key: "ArrowLeft" });
    expect(onVisiblePage).toHaveBeenCalledWith(1);
  });

  it("suit les numéros de page, pas les positions dans la liste", () => {
    // Le manifeste omet une page dont le rendu a échoué plutôt que d'inventer
    // ses dimensions : la position dans la liste n'est donc pas le numéro de
    // page. Compter en positions désignerait la mauvaise page dès qu'un rendu
    // manque.
    // Le retour en arrière est ce qui le prouve : compter en positions mène
    // alors hors de la liste, là où aller de l'avant retombait par hasard sur
    // la bonne page.
    const { onVisiblePage } = render(4, { pages: [1, 4, 5] });

    onVisiblePage.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Page suivante" }));
    expect(onVisiblePage).toHaveBeenCalledWith(5);

    onVisiblePage.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Page précédente" }));
    expect(onVisiblePage).toHaveBeenCalledWith(1);
  });

  it("ne sort pas du document", () => {
    const { onVisiblePage } = render(3);
    onVisiblePage.mockClear();

    // La flèche reste en place mais désactivée : la retirer ferait sauter la
    // mise en page à la dernière page.
    expect(screen.getByRole("button", { name: "Page suivante" })).toBeDisabled();
    expect(onVisiblePage).not.toHaveBeenCalled();
  });

  it("ne sort pas du document au clavier non plus", () => {
    // La flèche se désactive au bout ; le clavier, lui, n'a rien pour se
    // désactiver. Sans borne, il désignait une page qui n'existe pas.
    const { onVisiblePage, scroller } = render(3);
    onVisiblePage.mockClear();
    // On guette l'erreur, car sans cela le test passait sur un lecteur qui
    // tombait : désigner une page absente lève une exception, et « n'a pas
    // été appelé » devenait vrai pour la pire des raisons.
    const thrown: unknown[] = [];
    const watch = (event: ErrorEvent) => thrown.push(event.error);
    window.addEventListener("error", watch);

    fireEvent.keyDown(scroller, { key: "ArrowRight" });

    window.removeEventListener("error", watch);
    expect(thrown).toEqual([]);
    expect(onVisiblePage).not.toHaveBeenCalled();
  });

  it("n'offre pas de coins à tirer", () => {
    // On tire un coin pour tourner une feuille : c'est le geste de la double
    // page. Une bande qui défile ne se feuillette pas, et un coin qui ne
    // répond pas au geste promis est pire que son absence.
    render(2);

    expect(screen.getAllByRole("button", { name: "Page suivante" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Page précédente" })).toHaveLength(1);
  });

  it("garde les flèches hors du conteneur qui défile", () => {
    // Placées dedans, elles s'en vont avec les pages dès le premier geste — et
    // la bande défile toujours.
    const { scroller } = render(2);

    expect(scroller.contains(screen.getByRole("button", { name: "Page suivante" }))).toBe(
      false
    );
  });

  it("amène sous les yeux la page demandée d'ailleurs", () => {
    // La barre du haut, un lien de reprise : la page change sans que le
    // défilement l'ait annoncée, et il faut l'y conduire.
    const scrollIntoView = vi.fn();
    vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(scrollIntoView);

    render(2);

    expect(scrollIntoView).toHaveBeenCalledWith(expect.objectContaining({ inline: "center" }));
    vi.restoreAllMocks();
  });
});
