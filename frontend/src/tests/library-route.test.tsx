import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LibrarySection } from "@/routes/BibliothequePage";

afterEach(cleanup);

describe("LibrarySection", () => {
  it("renders favorites and progress without reading logs", () => {
    render(
      <LibrarySection
        favorites={[
          {
            document: {
              id: 1,
              slug: "doc",
              title: "Document favori",
              abstract: "Resume",
              language_code: "fr",
              publication_year: 2026,
              document_type: "open_resource",
              access_model: "free",
              domain: { id: 1, name: "Droit", slug: "droit" },
              authors: [],
              owner: null,
              page_count: 3,
              cover: null,
              access: { can_read: true, access_model: "free", reason: "free" }
            },
            created_at: "2026-07-30T10:00:00Z"
          }
        ]}
        progress={[]}
      />
    );

    expect(screen.getByText("Document favori")).toBeInTheDocument();
    expect(screen.queryByText(/historique page par page/i)).not.toBeInTheDocument();
  });

  it("lets readers add and remove known favorites from resumed documents", async () => {
    const onAddFavorite = vi.fn();
    const onRemoveFavorite = vi.fn();
    const document = {
      id: 2,
      slug: "lecture-en-cours",
      title: "Lecture en cours",
      abstract: "Resume",
      language_code: "fr",
      publication_year: 2026,
      document_type: "open_resource",
      access_model: "free",
      domain: { id: 1, name: "Droit", slug: "droit" },
      authors: [],
      owner: null,
      page_count: 3,
      cover: null,
      access: { can_read: true, access_model: "free", reason: "free" }
    };

    render(
      <LibrarySection
        favorites={[
          { document: { ...document, id: 3, title: "Deja favori" }, created_at: "2026-07-30T10:00:00Z" }
        ]}
        progress={[
          { document, last_page_number: 2, updated_at: "2026-07-30T10:00:00Z" },
          { document: { ...document, id: 3, title: "Deja favori" }, last_page_number: 1, updated_at: "2026-07-30T10:00:00Z" }
        ]}
        onAddFavorite={onAddFavorite}
        onRemoveFavorite={onRemoveFavorite}
      />
    );

    expect(screen.getByRole("heading", { name: "Reprendre la lecture" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ajouter aux favoris" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Retirer des favoris" })[0]);

    expect(onAddFavorite).toHaveBeenCalledWith(2);
    expect(onRemoveFavorite).toHaveBeenCalledWith(3);
  });
});
