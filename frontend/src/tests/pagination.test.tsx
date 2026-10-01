import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PaginationControls } from "@/components/catalog/PaginationControls";

/**
 * La barre de pagination.
 *
 * Elle encadrait « Page 1 sur 1 » de deux boutons morts et d'un sélecteur de
 * taille, sur toute la largeur de l'écran, pour six résultats : cela donnait à
 * un catalogue complet l'allure d'un catalogue tronqué.
 */
function reponse(
  count: number,
  { next = null, previous = null }: { next?: string | null; previous?: string | null } = {}
) {
  return { count, next, previous, results: [] };
}

describe("pagination", () => {
  it("se tait quand tout tient sur une page", () => {
    render(
      <PaginationControls response={reponse(6)} page={1} pageSize={12} path="/catalogue" />
    );

    expect(screen.getByText("6 résultats")).toBeInTheDocument();
    // Pas masqué par une classe : absent. jsdom n'applique aucune feuille de
    // style, donc un `hidden` de Tailwind y resterait « visible » et le test
    // passerait sur un écran encombré.
    expect(screen.queryByText(/Page 1 sur/)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Suivant" })).not.toBeInTheDocument();
  });

  it("se montre dès qu'il y a une page suivante", () => {
    render(
      <PaginationControls
        response={reponse(30, { next: "/api/v1/catalog/documents/?page=2" })}
        page={1}
        pageSize={12}
        path="/catalogue"
      />
    );

    expect(screen.getByText("Page 1 sur 3")).toBeVisible();
    expect(screen.getByRole("link", { name: "Suivant" })).toHaveAttribute(
      "href",
      "/catalogue?page=2&page_size=12"
    );
  });

  it("compte au singulier quand il n'y a qu'un résultat", () => {
    render(
      <PaginationControls response={reponse(1)} page={1} pageSize={12} path="/catalogue" />
    );

    expect(screen.getByText("1 résultat")).toBeInTheDocument();
  });

  it("le dit quand il n'y a rien", () => {
    render(
      <PaginationControls response={reponse(0)} page={1} pageSize={12} path="/catalogue" />
    );

    expect(screen.getByText("Aucun résultat")).toBeInTheDocument();
  });
});
