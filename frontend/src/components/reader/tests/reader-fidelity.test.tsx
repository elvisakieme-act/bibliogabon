import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
    image: null,
    ...overrides
  };
}

describe("page rendue", () => {
  it("affiche l'image de la page quand elle existe", () => {
    const { container } = render(
      <ReaderPage
        title="Thèse"
        page={page({ image: "/api/v1/reader/sessions/abc/pages/2/image/" })}
      />
    );

    const image = container.querySelector("img");
    expect(image).toHaveAttribute("src", "/api/v1/reader/sessions/abc/pages/2/image/");
  });

  it("superpose une couche texte sélectionnable", () => {
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

    expect(screen.getByText("Introduction")).toBeInTheDocument();
    expect(screen.getByText("générale")).toBeInTheDocument();
  });

  it("positionne chaque mot en pourcentages, jamais en pixels", () => {
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

    const word = screen.getByText("mot");
    expect(word.style.left).toBe("25%");
    expect(word.style.top).toBe("50%");
    expect(word.style.width).toBe("50%");
  });

  it("n'annonce pas l'image aux lecteurs d'écran", () => {
    // Le texte qui décrit l'image est juste au-dessus, dans la couche
    // transparente : une alternative le répéterait à chaque page.
    const { container } = render(
      <ReaderPage
        title="Thèse"
        page={page({ image: "/api/v1/reader/sessions/abc/pages/2/image/" })}
      />
    );

    expect(container.querySelector("img")).toHaveAttribute("alt", "");
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
