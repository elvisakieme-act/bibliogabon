import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SearchResult } from "@/api/types";
import { DocumentCard } from "@/components/catalog/DocumentCard";
import { SearchResultCard } from "@/components/catalog/SearchResultCard";
import { documentDetailReadLabel } from "@/routes/DocumentDetailPage";
import { createAppRouter } from "@/router";
import type { DocumentMetadata } from "@/api/types";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

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

  it.each([
    ["authentication_required", "Connexion requise"],
    ["entitlement_required", "Acces requis"]
  ])("renders %s as a non-link", (reason, label) => {
    render(
      <DocumentCard
        document={{
          ...document,
          access: { can_read: false, access_model: "institutional", reason }
        }}
      />
    );

    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: label })).not.toBeInTheDocument();
  });
});

describe("document detail access", () => {
  it.each([
    [{ can_read: true, access_model: "free", reason: "free" }, "Lire maintenant"],
    [{ can_read: false, access_model: "free", reason: "authentication_required" }, "Se connecter pour lire"],
    [{ can_read: false, access_model: "institutional", reason: "entitlement_required" }, "Acces requis"]
  ])("uses the required CTA label", (access, label) => {
    expect(documentDetailReadLabel({ ...document, access })).toBe(label);
  });
});

describe("SearchResultCard", () => {
  it("links to document detail only", () => {
    const result: SearchResult = {
      id: 20,
      title: "Recherche publique",
      slug: "recherche-publique",
      abstract: "Resume.",
      language_code: "fr",
      publication_year: 2026,
      domain: { name: "Droit", slug: "droit" },
      authors: ["Auteur Test"],
      access_model: "institutional",
      indexed_page_count: 10,
      score: 1,
      text_match: false
    };

    render(<SearchResultCard result={result} />);

    expect(screen.getByRole("link", { name: "Recherche publique" })).toHaveAttribute("href", "/documents/20");
    expect(screen.queryByRole("link", { name: /Lire/i })).not.toBeInTheDocument();
  });
});

describe("reader route", () => {
  it("registers a minimal lecture route for readable document CTAs", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createAppRouter({ history: createMemoryHistory({ initialEntries: ["/lecture/10"] }) });

    render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>);

    expect(await screen.findByRole("heading", { name: "Lecture" })).toBeInTheDocument();
  });
});

describe("search route query parameters", () => {
  it("forwards supported search and pagination parameters to the search endpoint", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createAppRouter({
      history: createMemoryHistory({
        initialEntries: ["/recherche?q=droit+public&domain=droit&language=fr&access=free&year=2026&page=2&page_size=8"]
      })
    });

    render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain(
      "http://127.0.0.1:8000/api/v1/search/?q=droit+public&domain=droit&language=fr&access=free&year=2026&page=2&page_size=8"
    );
  });
});
