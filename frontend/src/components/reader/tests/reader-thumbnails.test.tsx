import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/auth/AuthProvider";
import { ReaderThumbnailPanel } from "@/components/reader/ReaderThumbnailPanel";
import type { IiifManifest } from "@/features/reader/manifest";

/**
 * Le volet des pages.
 *
 * Les flèches suffisent à trois pages, pas à cent cinquante-sept. Ce que jsdom
 * peut vérifier est **ce qui est demandé au serveur** et ce que fait un clic ;
 * l'apparence du volet et le fait qu'on y reconnaisse la forme d'une page se
 * jugent à l'écran.
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
                    sizes: [{ width: 620, height: 877 }]
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

let fetchMock: ReturnType<typeof vi.fn>;

function afficher(props: Partial<Parameters<typeof ReaderThumbnailPanel>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const complet = {
    open: true,
    sessionKey: "x",
    manifest: manifest(),
    pageNumber: 2,
    onSelect: vi.fn(),
    onClose: vi.fn(),
    ...props
  };
  render(
    <AuthProvider>
      <QueryClientProvider client={client}>
        <ReaderThumbnailPanel {...complet} />
      </QueryClientProvider>
    </AuthProvider>
  );
  return complet;
}

function adresses() {
  return fetchMock.mock.calls.map(([url]) => String(url));
}

beforeEach(() => {
  fetchMock = vi.fn(async () => new Response(new Blob(["image"], { type: "image/webp" })));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("volet des pages", () => {
  it("ne montre rien tant qu'on ne l'a pas ouvert", () => {
    afficher({ open: false });

    expect(screen.queryByLabelText("Pages du document")).not.toBeInTheDocument();
    expect(adresses()).toHaveLength(0);
  });

  it("demande des vignettes, jamais des images de page", async () => {
    // C'est toute la différence : le point d'entrée des vignettes vérifie le
    // droit mais n'inscrit rien au journal d'accès. Passer par l'image de page
    // ferait enregistrer 157 pages lues à l'ouverture du volet.
    afficher();

    await waitFor(() => expect(adresses().length).toBeGreaterThan(0));
    expect(adresses().every((url) => url.includes("/thumbnail/"))).toBe(true);
    expect(adresses().some((url) => url.endsWith("/image/"))).toBe(false);
  });

  it("marque la page en cours", () => {
    afficher({ pageNumber: 2 });

    const courante = screen.getByRole("button", { current: "page" });
    expect(courante).toHaveTextContent("Page 2");
  });

  it("emmène à la page choisie", async () => {
    const props = afficher();

    await userEvent.click(screen.getByRole("button", { name: /Page 3/ }));

    expect(props.onSelect).toHaveBeenCalledWith(3);
  });

  it("se ferme par le voile comme par la croix", async () => {
    // Sur un téléphone le volet couvre la page : sans ces deux sorties, rien
    // ne dirait comment revenir au document.
    const props = afficher();

    for (const bouton of screen.getAllByRole("button", {
      name: "Fermer le volet des pages"
    })) {
      await userEvent.click(bouton);
    }

    expect(props.onClose).toHaveBeenCalledTimes(2);
  });
});
