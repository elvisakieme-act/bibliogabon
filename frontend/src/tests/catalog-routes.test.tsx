import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentCard } from "@/components/catalog/DocumentCard";
import type { DocumentMetadata } from "@/api/types";

const document: DocumentMetadata = {
  id: 10,
  slug: "droit-public",
  title: "Droit public gabonais",
  abstract: "Resume public.",
  language_code: "fr",
  publication_year: 2026,
  document_type: "open_resource",
  access_model: "free",
  domain: { id: 1, name: "Droit", slug: "droit" },
  authors: [{ id: 1, display_name: "Auteur Test", role: "author" }],
  owner: null,
  page_count: 12,
  cover: null,
  access: { can_read: true, access_model: "free", reason: "free" }
};

describe("DocumentCard", () => {
  it("renders public metadata and a read CTA without download links", () => {
    render(<DocumentCard document={document} />);

    expect(screen.getByText("Droit public gabonais")).toBeInTheDocument();
    expect(screen.getByText("Droit")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Lire/i })).toHaveAttribute(
      "href",
      "/lecture/10"
    );
    expect(screen.queryByText(/Telecharger/i)).not.toBeInTheDocument();
  });
});
