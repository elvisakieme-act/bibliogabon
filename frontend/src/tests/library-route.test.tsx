import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LibrarySection } from "@/routes/BibliothequePage";

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
});
