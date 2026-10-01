import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DocumentMetadata } from "@/api/types";
import { CoverShelf } from "@/components/home/CoverShelf";

/**
 * Les documents eux-mêmes, en guise de preuve.
 *
 * L'accroche montrait une photo d'archives : des étudiants qui pourraient
 * être ceux de n'importe quelle université du monde. Ces couvertures sont ce
 * que cette bibliothèque contient, et c'est le seul argument qu'aucun
 * concurrent ne peut copier.
 */
function document(overrides: Partial<DocumentMetadata> = {}): DocumentMetadata {
  return {
    id: 1,
    slug: "un-document",
    title: "Thèse : littérature gabonaise contemporaine",
    abstract: "Résumé.",
    language_code: "fr",
    publication_year: 2022,
    document_type: {
      id: 3,
      name: "Thèse",
      slug: "these",
      icon: "graduation-cap",
      color: "#2563EB"
    },
    category: "student_work",
    access_model: "free",
    domain: { id: 1, name: "Lettres", slug: "lettres" },
    authors: [],
    owner: null,
    page_count: 3,
    cover: "/api/v1/catalog/documents/1/cover/",
    access: { can_read: true, access_model: "free", reason: "" },
    ...overrides
  };
}

describe("étagère de couvertures", () => {
  it("montre les documents et mène à chacun", () => {
    render(<CoverShelf documents={[document(), document({ id: 2, title: "Cardiologie" })]} />);

    const liens = screen.getAllByRole("link");
    expect(liens).toHaveLength(2);
    expect(liens[0]).toHaveAttribute("href", "/documents/1");
    expect(liens[1]).toHaveAttribute("href", "/documents/2");
  });

  it("écarte les documents sans couverture plutôt que d'afficher un trou", () => {
    // Un document ingéré avant le tuilage n'a pas de couverture. L'afficher
    // quand même laisserait un rectangle vide au milieu du rayonnage, ce qui
    // dit l'inverse de ce que la section est censée dire.
    render(<CoverShelf documents={[document({ cover: null }), document({ id: 2 })]} />);

    expect(screen.getAllByRole("link")).toHaveLength(1);
  });

  it("ne rend rien quand aucun document n'a de couverture", () => {
    const { container } = render(<CoverShelf documents={[document({ cover: null })]} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("nomme chaque document sans doubler l'image", () => {
    // L'image porte `alt=""` et le titre vit dans un texte réservé aux
    // lecteurs d'écran : une alternative qui répéterait le titre le ferait
    // annoncer deux fois, puisque le lien le porte déjà.
    const { container } = render(<CoverShelf documents={[document()]} />);

    expect(container.querySelector("img")).toHaveAttribute("alt", "");
    expect(
      screen.getByRole("link", { name: "Thèse : littérature gabonaise contemporaine" })
    ).toBeInTheDocument();
  });
});
