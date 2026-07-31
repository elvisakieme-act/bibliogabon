import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DocumentMetadata } from "@/api/types";
import { tokenStore } from "@/auth/tokenStore";
import { createAppRouter } from "@/router";
import { LibrarySection } from "@/routes/BibliothequePage";

afterEach(() => {
  cleanup();
  tokenStore.clear();
  vi.unstubAllGlobals();
});

function libraryDocument(id: number, title: string): DocumentMetadata {
  return {
    id,
    slug: `document-${id}`,
    title,
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
}

function renderLibraryRoute() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter({
    history: createMemoryHistory({ initialEntries: ["/bibliotheque"] })
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

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
    expect(screen.getAllByRole("link", { name: "Reprendre" })[0]).toHaveAttribute(
      "href",
      "/lecture/2?page=2"
    );
    await userEvent.click(screen.getByRole("button", { name: "Ajouter aux favoris" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Retirer des favoris" })[0]);

    expect(onAddFavorite).toHaveBeenCalledWith(2);
    expect(onRemoveFavorite).toHaveBeenCalledWith(3);
  });

  it("uses API counts and incrementally loads all library result pages", async () => {
    tokenStore.set({ access: "access-token", refresh: "refresh-token" });
    const favoriteOne = libraryDocument(11, "Premier favori");
    const favoriteTwo = libraryDocument(12, "Deuxieme favori");
    const progressOne = libraryDocument(21, "Premiere lecture");
    const progressTwo = libraryDocument(22, "Deuxieme lecture");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/v1/me/") {
        return new Response(JSON.stringify({
          id: 1,
          email: "reader@example.ga",
          display_name: "Reader",
          account_type: "individual"
        }));
      }
      if (url.pathname === "/api/v1/me/favorites/") {
        const page = url.searchParams.get("page") ?? "1";
        return new Response(JSON.stringify(page === "1" ? {
          count: 2,
          next: "http://127.0.0.1:8000/api/v1/me/favorites/?page=2",
          previous: null,
          results: [{ document: favoriteOne, created_at: "2026-07-30T10:00:00Z" }]
        } : {
          count: 2,
          next: null,
          previous: "http://127.0.0.1:8000/api/v1/me/favorites/?page=1",
          results: [{ document: favoriteTwo, created_at: "2026-07-31T10:00:00Z" }]
        }));
      }
      if (url.pathname === "/api/v1/me/reading-progress/") {
        const page = url.searchParams.get("page") ?? "1";
        return new Response(JSON.stringify(page === "1" ? {
          count: 2,
          next: "http://127.0.0.1:8000/api/v1/me/reading-progress/?page=2",
          previous: null,
          results: [{
            document: progressOne,
            last_page_number: 1,
            updated_at: "2026-07-30T10:00:00Z"
          }]
        } : {
          count: 2,
          next: null,
          previous: "http://127.0.0.1:8000/api/v1/me/reading-progress/?page=1",
          results: [{
            document: progressTwo,
            last_page_number: 2,
            updated_at: "2026-07-31T10:00:00Z"
          }]
        }));
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderLibraryRoute();

    expect(await screen.findByText("Premier favori")).toBeInTheDocument();
    expect(screen.getByText("Premiere lecture")).toBeInTheDocument();
    const stats = screen.getByLabelText("Apercu de la bibliotheque");
    expect(within(stats).getAllByText("2")).toHaveLength(2);
    expect(screen.queryByText("Deuxieme favori")).not.toBeInTheDocument();
    expect(screen.queryByText("Deuxieme lecture")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Voir plus de favoris" }));
    await userEvent.click(screen.getByRole("button", { name: "Voir plus de lectures" }));

    expect(await screen.findByText("Deuxieme favori")).toBeInTheDocument();
    expect(await screen.findByText("Deuxieme lecture")).toBeInTheDocument();
    expect(screen.getByText("Premier favori")).toBeInTheDocument();
    expect(screen.getByText("Premiere lecture")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain(
        "http://127.0.0.1:8000/api/v1/me/favorites/?page=2"
      );
      expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain(
        "http://127.0.0.1:8000/api/v1/me/reading-progress/?page=2"
      );
    });
  });
});
